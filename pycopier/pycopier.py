import os
import shutil

from multiprocessing.pool import ThreadPool
from multiprocessing import TimeoutError

# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
try:
    from os import scandir, walk
except ImportError:
    from scandir import scandir, walk

class CopyObject(object):
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination

class PyCopier(object):
    def __init__(self, source, destination, numWorkers=8):
        self.source = source
        self.destination = destination

        self.numWorkers = numWorkers

    def execute(self):
        pool = ThreadPool(processes=self.numWorkers)
        results = []

        for root, dirs, files in walk(self.source):
            destDir = os.path.join(self.destination, os.path.relpath(root, self.source))

            # todo... should i let errors slide
            try:
                os.mkdir(destDir)
            except OSError:
                pass

            for file in files:
                fullSrcPath = os.path.join(root, file)
                destFile = os.path.join(destDir, file)
                results.append(pool.apply_async(shutil.copyfile, (fullSrcPath, destFile,)))
                # todo... what if results is really long? Should we clear them as we go


        for i in results:
            i.get() # should raise on issue... i think

        pool.close()
        pool.join()

        return results