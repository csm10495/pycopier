import argparse
import sys

import pycopier

def coerceArgsToArgparseCompatible(args):
    '''
    Turns /MT:<num> into /MT <num> ... without the user knowing.
        This is to keep compatibility with robocopy
    '''
    args = list(args)
    for idx, arg in enumerate(args):
        if arg.startswith('/MT:') and arg.count(':') == 1:
            args[idx] = '/MT'
            args.insert(idx + 1, arg.split(':')[-1])
        elif arg.startswith('--'):
            # coerce to // prefix
            args[idx]= arg.replace('-', '/', 2)
        elif arg.startswith('-'):
            # coerce to / prefix
            args[idx]= arg.replace('-', '/', 1)

    return args

def main():
    parser = argparse.ArgumentParser(prefix_chars='/', usage="\n" + pycopier.ASCII_ART + "\n ... a Python 3 replacement for Robocopy, including multithreaded copy.")

    arg_group_robocopy = parser.add_argument_group("Robocopy Arguments", "Arguments that more/less match Robocopy")
    arg_group_robocopy.add_argument('Source', type=str, nargs=1, help='Specifies the path to the source directory.')
    arg_group_robocopy.add_argument('Destination', type=str, nargs=1, help='Specifies the path to the destination directory.')
    arg_group_robocopy.add_argument('/MT', type=int, help='Creates multi-threaded copies with N threads. The default value for N is 8', default=8)
    arg_group_robocopy.add_argument('/create', action='store_true', help='Creates a directory tree and zero-length files only.')
    arg_group_robocopy.add_argument('/quit', action='store_true', help='Quits after processing command line (to view parameters).')
    arg_group_robocopy.add_argument('/purge', action='store_true', help='Deletes destination files and directories that no longer exist in the source.')
    arg_group_robocopy.add_argument('/move', action='store_true', help='Moves files and directories, and deletes them from the source after they are copied.')
    arg_group_robocopy.add_argument('/copyall', action='store_true', help='Copies all file information.')
    arg_group_robocopy.add_argument('/s', action='store_true', help='Copies subdirectories. Note that this option excludes empty directories. (robocopy\'s /e option for subdirectories including empties is default for pycopier)')

    # options specific to pycopier (and not in robocopy)
    arg_group_robocopy = parser.add_argument_group("PyCopier Arguments", "Arguments that are specific to PyCopier")
    arg_group_robocopy.add_argument('/quiet', action='store_true', help='If set, be completely quiet during execution.')

    argv = coerceArgsToArgparseCompatible(sys.argv)
    args = parser.parse_args(argv[1:])

    p = pycopier.PyCopier(source=args.Source[0],
                      destination=args.Destination[0],
                      numWorkers=args.MT,
                      zeroLengthFiles=args.create,
                      purgeDestination=args.purge,
                      move=args.move,
                      copyPermissions=args.copyall,
                      ignoreEmptyDirectories=args.s,
                      quiet=args.quiet,
                      skipSameLookingFiles=True, # not sure if this matches robocopy or not
    )

    if args.quit:
        print(p)
        sys.exit(0)

    p.execute()

    # assume success at this point.
    # todo: need to check for errors and keep track of them in PyCopier object
    #    based off that change the error code to 8
    sys.exit(1)

if __name__ == '__main__':
    main()