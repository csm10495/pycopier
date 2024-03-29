'''
Brief:
    pycopier.py - Main implementation for PyCopier.

Author(s):
    Charles Machalow (MIT License)
'''
import decimal
import os
import re
import shutil
import sys
import threading
import time
from multiprocessing import TimeoutError
from multiprocessing.pool import ThreadPool
import warnings

# don't show warnings in humaize
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import humanize

from scandir import walk

__version__ = '1.2.0'

ASCII_ART = r'''
    ____        ______            _
   / __ \__  __/ ____/___  ____  (_)__  _____
  / /_/ / / / / /   / __ \/ __ \/ / _ \/ ___/
 / ____/ /_/ / /___/ /_/ / /_/ / /  __/ /
/_/    \__, /\____/\____/ .___/_/\___/_/
      /____/           /_/                   %s
''' % __version__

class PyCopier(object):
    def __init__(self, source, destination, numWorkers=16, bufferSize=8192, reportingTimeDelta=.1, zeroLengthFiles=False,
                ignoreEmptyDirectories=False, copyPermissions=False, move=False, purgeDestination=False, skipSameLookingFiles=False,
                ignoreErrorOnCopy=False, quiet=False):
        self.source = source
        self.destination = destination

        self.numWorkers = numWorkers
        self.bufferSize = bufferSize
        self.reportingTimeDelta = reportingTimeDelta
        self.zeroLengthFiles = zeroLengthFiles
        self.ignoreEmptyDirectories = ignoreEmptyDirectories
        self.copyPermissions = copyPermissions
        self.move = move
        self.purgeDestination = purgeDestination
        self.skipSameLookingFiles = skipSameLookingFiles
        self.ignoreErrorOnCopy = ignoreErrorOnCopy
        self.quiet = quiet

        self.copiedDataBytes = 0
        self.numberOfPurgedFiles = 0
        self.numberOfSkippedCopies = 0
        self.copiedDataBytesLock = threading.Lock()
        self.numberOfPurgedFilesLock = threading.Lock()
        self.numberOfSkippedCopiesLock = threading.Lock()

        # for reporting current speed
        self._nextReportTime = 0
        self._reportedDataBytes = 0

        self._done = True

    @classmethod
    def __camelCaseToTitleCaseWithSpaces(cls, s):
        return ' '.join([a.title() for a in re.sub( r"([A-Z])", r" \1", s).split()])

    def __str__(self):
        d = {}
        for name in sorted(dir(self)):
            thing = getattr(self, name)
            if not name.startswith('_') and isinstance(thing, (int, bool, str)):
                d[self.__camelCaseToTitleCaseWithSpaces(name)] = thing

        # now go through d and print
        longestName = max([len(x) for x in d.keys()]) + 1

        retStr = ''
        for key, value in d.items():
            retStr += key.ljust(longestName) + ": " + str(value) + "\n"

        return retStr

    @classmethod
    def statMatch(cls, srcStat, destStat):
        if srcStat.st_size != destStat.st_size:
            return False

        # In Python 2, certain timestamps tend to not be precise.
        # See https://stackoverflow.com/questions/17086426/file-modification-times-not-equal-after-calling-shutil-copystatfile1-file2-un
        #  for more info.
        if sys.version_info.major == 2:
            def coerce(num):
                # grossly inaccurate.
                return int(num)

            if (coerce(srcStat.st_mtime) != coerce(destStat.st_mtime)) or \
                (coerce(srcStat.st_atime) != coerce(destStat.st_atime)):
                return False
        else:
            # In Python 3, we seem to always have the same granularity
            if (srcStat.st_mtime != destStat.st_mtime or \
                srcStat.st_atime != destStat.st_atime):
                return False

        return True

    def _copyFile(self, source, destination):
        copiedDataLength = 0

        if self.skipSameLookingFiles:
            try:
                statDest = os.stat(destination)
            except FileNotFoundError:
                # destination doesn't exist... can't check
                pass
            else:
                statSource = os.stat(source)
                if self.statMatch(statSource, statDest):
                    # skip!
                    self.addToSkippedCopies(1)
                    return

        nextReportTime = time.time() + self.reportingTimeDelta

        try:
            with open(source, 'rb') as srcFile:
                with open(destination, 'wb') as destFile:
                    if not self.zeroLengthFiles:
                        while True:

                            if time.time() > nextReportTime:
                                self.addCopiedDataBytes(copiedDataLength)

                                copiedDataLength = 0
                                nextReportTime = time.time() + self.reportingTimeDelta

                            buf = srcFile.read(self.bufferSize)
                            if not buf:
                                break

                            copiedDataLength += len(buf)
                            destFile.write(buf)
        except Exception:
            if not self.ignoreErrorOnCopy:
                raise
        else:
            if self.copyPermissions:
                shutil.copystat(source, destination)

            if self.move:
                os.remove(source)

        self.addCopiedDataBytes(copiedDataLength)

    def _cleanDestinationDirectory(self, destinationDirectory, srcListing):
        count = 0
        for path in os.listdir(destinationDirectory):
            if path not in srcListing:
                fullPath = os.path.join(destinationDirectory, path)
                if os.path.isfile(fullPath):
                    os.remove(fullPath)
                    count += 1
                elif os.path.isdir(fullPath):
                    # clear all, but also counts all
                    self._cleanDestinationDirectory(fullPath, [])

        self.addToPurgedFileCount(count)

    def addCopiedDataBytes(self, numBytes):
        with self.copiedDataBytesLock:
            self.copiedDataBytes += numBytes

    def addToPurgedFileCount(self, numFiles):
        with self.numberOfPurgedFilesLock:
            self.numberOfPurgedFiles += numFiles

    def addToSkippedCopies(self, numSkipped):
        with self.numberOfSkippedCopiesLock:
            self.numberOfSkippedCopies += numSkipped

    def getCopiedDataBytes(self):
        with self.copiedDataBytesLock:
            return self.copiedDataBytes

    def getPurgedFileCount(self):
        with self.numberOfPurgedFilesLock:
            return self.numberOfPurgedFiles

    def getSkippedCopiesCount(self):
        with self.numberOfSkippedCopiesLock:
            return self.numberOfSkippedCopies

    def checkAndPrintSpeedIfNeeded(self):
        if time.time() > self._nextReportTime:
            copiedDataBytes = self.getCopiedDataBytes()
            deltaBytes = copiedDataBytes - self._reportedDataBytes
            if not self.quiet:
                sys.stdout.write("\rSpeed: ~%s per second".ljust(50) % (humanize.naturalsize(float(deltaBytes) / self.reportingTimeDelta)))
            self._reportedDataBytes += deltaBytes
            self._nextReportTime = time.time() + self.reportingTimeDelta

    def _submitOperations(self):
        if self._done:
            self.pool = ThreadPool(processes=self.numWorkers)
            self._done = False

        if not self.quiet:
            print ("Submitting Operations for %s -> %s" % (self.source, self.destination))

        results = []

        if os.path.isdir(self.source):
            for root, dirs, files in walk(self.source):
                self.checkAndPrintSpeedIfNeeded()

                destDir = os.path.abspath(os.path.join(self.destination, os.path.relpath(root, self.source)))

                if self.purgeDestination:
                    results.append(self.pool.apply_async(self._cleanDestinationDirectory, (destDir, set(files + dirs),)))

                if len(files) == 0 and len(dirs) == 0 and self.ignoreEmptyDirectories:
                    continue

                try:
                    os.mkdir(destDir)
                except OSError:
                    pass

                # todo... thread out this?
                if self.copyPermissions:
                    try:
                        shutil.copystat(root, destDir)
                    except:
                        ''' todo: why does this happen?
                        FileNotFoundError: [WinError 2] The system cannot find the file specified: 'E:\\csm10495\\AppData\\Local\\Packages\\CanonicalGroupLimited.UbuntuonWindows_79rhkp1fndgsc\\LocalState\\rootfs\\home\\csm10495\\cling-build\\cling-src\\tools\\clang\\test\\Driver\\Inputs\\gentoo_linux_gcc_multi_version_tree\\usr\\lib\\gcc\\x86_64-pc-linux-gnu\\4.9.3\\32'
                        '''
                        if not self.ignoreErrorOnCopy:
                            raise

                for file in files:
                    fullSrcPath = os.path.join(root, file)
                    destFile = os.path.join(destDir, file)
                    results.append(self.pool.apply_async(self._copyFile, (fullSrcPath, destFile,)))
                    # todo... what if results is really long? Should we clear them as we go?
        elif os.path.isfile(self.source):
            # single file. Submit a single submission for it.

            # if the destination is a dir, put the file (with the current basename) in the destination.
            if os.path.isdir(self.destination):
                destFile = os.path.join(self.destination, os.path.basename(self.source))
            else:
                destFile = self.destination

            # ensure output directory exists
            destDir = os.path.dirname(destFile)
            try:
                os.mkdir(destDir)
            except OSError:
                pass

            results.append(self.pool.apply_async(self._copyFile, (self.source, destFile,)))

            if self.purgeDestination:
                # delete everything in destination other than this new file
                results.append(self.pool.apply_async(self._cleanDestinationDirectory, (destDir, [os.path.basename(destFile)],)))

        else:
            raise ValueError("%s is not a directory or file path" % self.source)

        if not self.quiet:
            sys.stdout.write("\rOperation submission complete!              \n")

        return results

    def execute(self):
        if not self.quiet:
            print (ASCII_ART)
            print (str(self))

        startTime = time.time()
        self.copiedDataBytes = 0
        self.numberOfPurgedFiles = 0
        self.numberOfSkippedCopies = 0
        self._reportedDataBytes = 0
        self._nextReportTime = 0

        results = self._submitOperations()

        nextReportTime = time.time() + self.reportingTimeDelta

        if not self.quiet:
            sys.stdout.write('\n')

        for idx, itm in enumerate(results):
            while True:
                self.checkAndPrintSpeedIfNeeded()
                try:
                    itm.get(timeout=.001)
                    break
                except TimeoutError:
                    pass

        if not self.quiet:
            sys.stdout.write('\n')

        self.pool.close()
        self.pool.join()

        if self.move:
            if os.path.isdir(self.source):
                shutil.rmtree(self.source)
            # if we did a file, it would have been deleted already by _copyFile

        self._done = True

        endTime = time.time()

        if not self.quiet:
            print ("-" * 20)
            print ("Total Runtime:       %.2f seconds" % (endTime - startTime))
            print ("Total Data Copied:   %s" % (humanize.naturalsize(self.getCopiedDataBytes())))
            print ("Avg Speed:           %s per second" % (humanize.naturalsize(self.getCopiedDataBytes() / (endTime - startTime))))
            if self.purgeDestination:
                print ("Purged File Count:   %d" % self.getPurgedFileCount())
            if self.skipSameLookingFiles:
                print ("Skipped Copy Count:  %d" % self.getSkippedCopiesCount())

if __name__ == '__main__':
    pass

