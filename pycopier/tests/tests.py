import contextlib
import filecmp
import io
import os
import random
import shutil
import sys
import time
import unittest

import pytest
import scandir

from pycopier.pycopier import PyCopier

THIS_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

class _TestDirectory(object):
    '''
    quick object used to generate a directory of files/folders for copying
    '''
    def __init__(self, maxDepth=5, maxFilesPerDepth=3, minFilesPerDepth=0, maxFoldersPerDepth=3, minFoldersPerDepth=0, sourceDirectory=None, seeds=None):
        self.maxFilesPerDepth = maxFilesPerDepth
        self.maxFoldersPerDepth = maxFoldersPerDepth

        self.minFilesPerDepth = minFilesPerDepth
        self.minFoldersPerDepth = minFoldersPerDepth
        self.maxDepth = maxDepth
        if seeds is None:
            self.seeds = [random.randint(0, 0xffff) for i in range(0xff)]
        else:
            self.seeds = seeds

        self.seedIdx = 0
        self._hasBeenCreated = False

        if sourceDirectory is None:
            self.sourceDirectory = os.path.join(THIS_DIRECTORY, 'test_source_directory_' + str(random.randint(0, 0xFFFFFFFF)))
        else:
            self.sourceDirectory = sourceDirectory

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isdir(self.sourceDirectory):
            shutil.rmtree(self.sourceDirectory)

    def create(self):
        # to generate same structure again
        self.seedIdx = 0
        random.seed(self.seedIdx)

        os.makedirs(self.sourceDirectory)

        numFilesAtThisDepth = random.randint(self.minFilesPerDepth, self.maxFilesPerDepth)
        for i in range(numFilesAtThisDepth):
            fullFilePath = os.path.join(self.sourceDirectory, 'file_%d.txt' % i)
            assert not os.path.isfile(fullFilePath), "File already exists!"
            with open(fullFilePath, 'w') as f:
                f.write('ABC' * random.randint(0, 0xFF))

        if self.maxDepth > 1:
            numFoldersAtThisDepth = random.randint(self.minFoldersPerDepth, self.maxFoldersPerDepth)
            for i in range(numFoldersAtThisDepth):
                fullFolderPath = os.path.join(self.sourceDirectory, 'folder_%d' % i)
                t = _TestDirectory(sourceDirectory=fullFolderPath, maxDepth=self.maxDepth - 1, seeds=self.seeds[self.seedIdx:])
                self.seedIdx += 1
                t.create()

        return self.sourceDirectory

    def _dirCmpMatch(self, dirCmpObject, shallow, checkPermissions, zeroLengthFiles, move, ignoreExtraRight):
        if move:
            self.create()

        try:
            if dirCmpObject.left_list != dirCmpObject.right_list:
                err = True
                if ignoreExtraRight:
                    if not dirCmpObject.left_only and dirCmpObject.right_only :
                        err = False

                if err:
                    print ("Match failure (missing/extra files)")
                    print ("Left: %s" % dirCmpObject.left_list)
                    print ("Right: %s" % dirCmpObject.right_list)
                    dirCmpObject.report()
                    return False

            for file in dirCmpObject.common_files:
                left = os.path.join(dirCmpObject.left, file)
                right = os.path.join(dirCmpObject.right, file)

                if zeroLengthFiles:
                    if os.path.getsize(right) != 0:
                        print ("%s should be size 0" % right)
                        return False
                else:
                    if not filecmp.cmp(
                        left,
                        right,
                        shallow=shallow
                    ):
                        print ("Match failure: \n%s\n%s\n don't match" % (left, right))
                        return False

                    if checkPermissions:
                        leftStat = os.stat(left)
                        rightStat = os.stat(right)

                        if leftStat.st_mode != rightStat.st_mode or \
                            leftStat.st_mtime != rightStat.st_mtime or \
                            leftStat.st_atime  != rightStat.st_atime:
                            print ("Permission mismatch: \n%s\n%s\n don't match" % (left, right))
                            return False


            for name, dirCmp in dirCmpObject.subdirs.items():
                # move must always be False in nested scenarios, since we would have already recreated the src
                if not self._dirCmpMatch(dirCmp, shallow, checkPermissions, zeroLengthFiles, move=False, ignoreExtraRight=ignoreExtraRight):
                    return False

            return True
        finally:
            if move:
                # delete src.
                self.__exit__(None, None, None)

    def checkMatch(self, destinationDirectory, shallow=True, checkPermissions=False, zeroLengthFiles=False, move=False, ignoreExtraRight=False):
        myDirCmp = filecmp.dircmp(self.sourceDirectory, destinationDirectory)
        return self._dirCmpMatch(myDirCmp, shallow, checkPermissions, zeroLengthFiles, move, ignoreExtraRight)

class PyCopierTestBase(object):
    @contextlib.contextmanager
    def getNewDestination(self):
        dest = os.path.join(THIS_DIRECTORY, str(random.randint(0, 0xFFFFFFFF)))
        try:
            yield dest
        finally:
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            elif os.path.isfile(dest):
                os.remove(dest)

class PyCopierUnitTests(unittest.TestCase, PyCopierTestBase):
    '''
    unit-style tests
    '''
    def test_generic_copy_file(self):
        p = PyCopier(source=None, destination=None)
        with self.getNewDestination() as dest:
            p._copyFile(__file__, dest)
            assert os.path.isfile(dest)
            assert filecmp.cmp(__file__, dest, shallow=False)

        assert p.getCopiedDataBytes() == os.path.getsize(__file__)
        assert p.getSkippedCopiesCount() == 0

    def test_skip_same_looking_file(self):
        p = PyCopier(source=None, destination=None, skipSameLookingFiles=True)
        with self.getNewDestination() as dest:
            shutil.copy2(__file__, dest)
            p._copyFile(__file__, dest)

        assert p.getSkippedCopiesCount() == 1
        assert p.getCopiedDataBytes() == 0

    def test_skip_same_looking_file_doesnt_happen_if_meta_doesnt_match(self):
        p = PyCopier(source=None, destination=None, skipSameLookingFiles=True)
        with self.getNewDestination() as dest:
            shutil.copy(__file__, dest)
            p._copyFile(__file__, dest)

        assert p.getSkippedCopiesCount() == 0
        assert p.getCopiedDataBytes() == os.path.getsize(__file__)

    def test_errors_ignored_on_copy(self):
        p = PyCopier(source=None, destination=None, ignoreErrorOnCopy=True)
        with self.getNewDestination() as dest:
            p._copyFile("/fake/file", dest)

        # nothing raised... nothing copied
        assert p.getSkippedCopiesCount() == 0
        assert p.getCopiedDataBytes() == 0

    def test_errors_not_ignored_on_copy(self):
        p = PyCopier(source=None, destination=None, ignoreErrorOnCopy=False)
        with self.getNewDestination() as dest:
            with pytest.raises(Exception):
                p._copyFile("/fake/file", dest)

        # nothing raised... nothing copied
        assert p.getSkippedCopiesCount() == 0
        assert p.getCopiedDataBytes() == 0

    def test_cleaning_directory(self):
        p = PyCopier(source=None, destination=None, ignoreErrorOnCopy=False)
        with _TestDirectory() as t:
            t.create()

            # count files
            numFiles = 0
            for path, dirs, files in os.walk(t.sourceDirectory):
                numFiles += len(files)

            p._cleanDestinationDirectory(t.sourceDirectory, [])

        # nothing raised... nothing copied
        assert p.getPurgedFileCount() == numFiles

class PyCopierFunctionalTests(unittest.TestCase, PyCopierTestBase):
    '''
    functional-style tests
    '''
    def test_generic_copy_various_worker_count(self):
        for numWorkers in range(1, 16):
            with _TestDirectory() as t:
                t.create()
                with self.getNewDestination() as dest:
                    PyCopier(t.sourceDirectory, dest, numWorkers=numWorkers).execute()
                    assert t.checkMatch(dest)

    def test_generic_copy_weird_buffer_size(self):
        for bufferSize in [1024, 4096, 8192, 1, 2]:
            with _TestDirectory() as t:
                t.create()
                with self.getNewDestination() as dest:
                    PyCopier(t.sourceDirectory, dest, bufferSize=bufferSize).execute()
                    assert t.checkMatch(dest)

    def test_zero_length_copy(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestination() as dest:
                PyCopier(t.sourceDirectory, dest, zeroLengthFiles=True).execute()
                assert t.checkMatch(dest, zeroLengthFiles=True)

    def test_permission_copy(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestination() as dest:
                PyCopier(t.sourceDirectory, dest, copyPermissions=True).execute()
                assert t.checkMatch(dest, checkPermissions=True)

    def test_move(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestination() as dest:
                PyCopier(t.sourceDirectory, dest, move=True).execute()
                assert t.checkMatch(dest, move=True)

    def test_purge_destination(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestination() as dest:
                os.mkdir(dest)
                fileThatShouldBePurged = os.path.join(dest, 'test_tmp')
                with open(fileThatShouldBePurged, 'w') as f:
                    f.write('test')

                PyCopier(t.sourceDirectory, dest, purgeDestination=False).execute()
                assert os.path.exists(fileThatShouldBePurged)
                assert t.checkMatch(dest, ignoreExtraRight=True)

                PyCopier(t.sourceDirectory, dest, purgeDestination=True).execute()
                assert not os.path.exists(fileThatShouldBePurged)
                assert t.checkMatch(dest)

    def test_quiet_param(self):
        with _TestDirectory() as t:
            t.create()
            output = io.StringIO()
            with self.getNewDestination() as dest:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    PyCopier(t.sourceDirectory, dest, quiet=True).execute()

                assert t.checkMatch(dest)

            assert output.getvalue() == '', "Nothing should go to output if quiet"

    def test_copy_single_file(self):
        with self.getNewDestination() as dest:
            p = PyCopier(source=__file__, destination=dest)
            p.execute()
            assert p.getCopiedDataBytes() == os.path.getsize(__file__)
            assert filecmp.cmp(__file__, dest, shallow=False)

    def test_copy_single_file_into_dir(self):
        with self.getNewDestination() as dest:
            os.mkdir(dest)

            p = PyCopier(source=__file__, destination=dest)
            p.execute()
            assert p.getCopiedDataBytes() == os.path.getsize(__file__)
            assert filecmp.cmp(__file__, os.path.join(dest, os.path.basename(__file__)), shallow=False)

    def test_copy_single_file_into_dir_and_purge(self):
        with self.getNewDestination() as dest:
            os.mkdir(dest)
            TEST_PATH = os.path.join(dest, 'test')
            with open(TEST_PATH, 'wb') as f:
                f.write(b'abc' * 10)

            p = PyCopier(source=__file__, destination=dest, purgeDestination=True)
            p.execute()

            assert p.getCopiedDataBytes() == os.path.getsize(__file__)
            assert filecmp.cmp(__file__, os.path.join(dest, os.path.basename(__file__)), shallow=False)
            assert not os.path.exists(TEST_PATH)

    def test_copy_single_file_with_move(self):
        with open(__file__, 'rb') as f:
            fileData = f.read()

        try:
            with self.getNewDestination() as dest:
                p = PyCopier(source=__file__, destination=dest, move=True)
                p.execute()
                assert p.getCopiedDataBytes() == len(fileData)
                with open(dest, 'rb') as f:
                    newFileData = f.read()

                assert fileData == newFileData
                assert not os.path.exists(__file__)
        finally:
            with open(__file__, 'wb') as f:
                f.write(fileData)
