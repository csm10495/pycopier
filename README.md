# PyCopier
[![Build status](https://csm10495.visualstudio.com/pycopier/_apis/build/status/pycopier-CI)](https://csm10495.visualstudio.com/pycopier/_build/latest?definitionId=5)

Supports Python 3.6 and later. If it doesn't work with your Python version, feel free to submit a PR. PRs are welcome!

A Python-based multi-threaded directory copier. This was created in the spirit of wanting to give a cross-platform way of doing a multi-threaded copy, in a way similar to Microsoft's Robocopy. Some params are implemented similarly to parameters of the same name from Robocopy. (Simple Robocopy calls may work with PyCopier by replacing robocopy.exe with pycopier.)

# Installation

To install, clone down and in the top pycopier directory run:

```
python -m pip install .
```
or
```
python -m pip install pycopier
```

# Simple Usage

After install, you can run via  ...

```
python -m pycopier SourceDir DestinationDir <optional params>
```
or
```
pycopier SourceDir DestinationDir <optional params>
```

# Extended Usage

```
    ____        ______            _
   / __ \__  __/ ____/___  ____  (_)__  _____
  / /_/ / / / / /   / __ \/ __ \/ / _ \/ ___/
 / ____/ /_/ / /___/ /_/ / /_/ / /  __/ /
/_/    \__, /\____/\____/ .___/_/\___/_/
      /____/           /_/                   1.0.0

 ... a Python 3 replacement for Robocopy, including multithreaded copy.

optional arguments:
  /h, //help   show this help message and exit

Robocopy Arguments:
  Arguments that more/less match Robocopy

  Source       Specifies the path to the source directory.
  Destination  Specifies the path to the destination directory.
  /MT MT       Creates multi-threaded copies with N threads. The default value
               for N is 8
  /create      Creates a directory tree and zero-length files only.
  /quit        Quits after processing command line (to view parameters).
  /purge       Deletes destination files and directories that no longer exist
               in the source.
  /move        Moves files and directories, and deletes them from the source
               after they are copied.
  /copyall     Copies all file information.
  /s           Copies subdirectories. Note that this option excludes empty
               directories. (robocopy's /e option for subdirectories including
               empties is default for pycopier)

PyCopier Arguments:
  Arguments that are specific to PyCopier

  /quiet       If set, be completely quiet during execution.
```

# Development

All development happens off of the master branch (or PRs to master). Once a 'release' is needed, versions, etc. will be updated in the master branch, tagged, and merged to the release branch. Nothing should be in the release branch that hasn't already been in the master branch.

# License
This project is made available via the MIT License
