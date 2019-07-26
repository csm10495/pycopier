'''
Brief:
    pycopier.py - Main implementation for PyCopier.

Author(s):
    Charles Machalow (MIT License)
'''
import os
import shutil
import sys
import threading
import time
from multiprocessing import TimeoutError
from multiprocessing.pool import ThreadPool

import humanize
from scandir import walk

class PyCopier(object):
    def __init__(self, source, destination, numWorkers=16, bufferSize=8192, reportingTimeDelta=.1, zeroLengthFiles=False,
                ignoreEmptyDirectories=False, copyPermissions=False, move=False, purgeDestination=False, skipSameLookingFiles=False,
                ignoreErrorOnCopy=False):
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
                if statSource.st_size == statDest.st_size and statSource.st_mtime == statDest.st_mtime:
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
                    shutil.rmtree(fullPath, ignore_errors=True)
                    count += 1

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
            sys.stdout.write("\rSpeed: ~%s per second".ljust(50) % (humanize.naturalsize(float(deltaBytes) / self.reportingTimeDelta)))
            self._reportedDataBytes += deltaBytes
            self._nextReportTime = time.time() + self.reportingTimeDelta

    def _submitOperations(self):
        if self._done:
            self.pool = ThreadPool(processes=self.numWorkers)
            self._done = False

        print ("Submitting Operations for %s -> %s" % (self.source, self.destination))

        results = []

        for root, dirs, files in walk(self.source):
            self.checkAndPrintSpeedIfNeeded()

            destDir = os.path.join(self.destination, os.path.relpath(root, self.source))

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
                    pass

            for file in files:
                fullSrcPath = os.path.join(root, file)
                destFile = os.path.join(destDir, file)
                results.append(self.pool.apply_async(self._copyFile, (fullSrcPath, destFile,)))
                # todo... what if results is really long? Should we clear them as we go?

        sys.stdout.write("\rOperation submission complete!              \n")

        return results

    def execute(self):
        startTime = time.time()
        self.copiedDataBytes = 0
        self.numberOfPurgedFiles = 0
        self.numberOfSkippedCopies = 0
        self._reportedDataBytes = 0
        self._nextReportTime = 0

        results = self._submitOperations()

        nextReportTime = time.time() + self.reportingTimeDelta
        sys.stdout.write('\n')
        for idx, itm in enumerate(results):
            while True:
                self.checkAndPrintSpeedIfNeeded()
                try:
                    itm.get(timeout=.001)
                    break
                except TimeoutError:
                    pass

        sys.stdout.write('\n')

        self.pool.close()
        self.pool.join()

        if self.move:
            shutil.rmtree(self.source)

        self._done = True

        endTime = time.time()
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

    ''' ... wip
    import argparse
    parser = argparse.ArgumentParser(prefix_chars='/')
    parser.add_argument('/MT', type=int)

    import pdb;pdb.set_trace()
    for idx, arg in enumerate(sys.argv):
        if arg.startswith('/MT:') and arg.count(':') == 1:
            sys.argv[idx] = '/MT'
            sys.argv.insert(idx + 1, arg.split(':')[-1])

    args = parser.parse_args()
    print (args)
    '''