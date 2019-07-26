import contextlib
import filecmp
import os
import scandir
import sys
import shutil
import random
import pytest
import unittest
import time

THIS_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

from ..pycopier import PyCopier

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

class PyCopierFunctionalTests(unittest.TestCase):
    '''
    functional-style tests
    '''
    @contextlib.contextmanager
    def getNewDestinationDirectory(self):
        dest = os.path.join(THIS_DIRECTORY, str(random.randint(0, 0xFFFFFFFF)))
        try:
            yield dest
        finally:
            if os.path.isdir(dest):
                shutil.rmtree(dest)

    def test_generic_copy_various_worker_count(self):
        for numWorkers in range(1, 16):
            with _TestDirectory() as t:
                t.create()
                with self.getNewDestinationDirectory() as dest:
                    PyCopier(t.sourceDirectory, dest, numWorkers=numWorkers).execute()
                    assert t.checkMatch(dest)

    def test_generic_copy_weird_buffer_size(self):
        for bufferSize in [1024, 4096, 8192, 1, 2]:
            with _TestDirectory() as t:
                t.create()
                with self.getNewDestinationDirectory() as dest:
                    PyCopier(t.sourceDirectory, dest, bufferSize=bufferSize).execute()
                    assert t.checkMatch(dest)

    def test_zero_length_copy(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestinationDirectory() as dest:
                PyCopier(t.sourceDirectory, dest, zeroLengthFiles=True).execute()
                assert t.checkMatch(dest, zeroLengthFiles=True)

    def test_permission_copy(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestinationDirectory() as dest:
                PyCopier(t.sourceDirectory, dest, copyPermissions=True).execute()
                assert t.checkMatch(dest, checkPermissions=True)

    def test_move(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestinationDirectory() as dest:
                PyCopier(t.sourceDirectory, dest, move=True).execute()
                assert t.checkMatch(dest, move=True)

    def test_purge_destination(self):
        with _TestDirectory() as t:
            t.create()
            with self.getNewDestinationDirectory() as dest:
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

