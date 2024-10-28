#!/usr/bin/env python3
"""command line utility to navigate file structure using bookmarks.

goto is a tool that allows you to quickly move between directories.
The basic workflow is as follows:

1. Use goto -n <root> to create a new root file
2. Edit the new json root file to configure the root
2. Use goto -s <root> to set the current root
3. Use goto <shortcut> to cd to the shortcut in the current root dir

All shortcuts are given relative to root dir.

File structures

config.json: contains overall settings, e.g. the current root dir

roots/: contains all available roots, one per file.  Has information
on each including abbreviation and path. Add new files here to include
more root directories. Use the "defaults" field to add extra sets of
shortcuts to this root directory. This is useful if you have a number
of directories with similar file structure. For example, if you have
multiple branches of the same repo checked out.

~/.config/goto-global contains global roots that are meant to be
checked into VCS and maintained across machines.

~/.config/goto-local contains local roots that are meant to be
specific to this machine.
"""

###############################################################################
# Imports                                                                     #
###############################################################################

import os
import argparse
import json
import sys
import subprocess

from os import path
from typing import Mapping, List, Any

###############################################################################
# Constants                                                                   #
###############################################################################

LOCAL_GOTO_DIR = path.expanduser("~/.config/goto-local")
GLOBAL_GOTO_DIR = path.expanduser("~/.config/goto-global")

CONFIG_FILEPATH = path.join(LOCAL_GOTO_DIR, "config.json")
GLOBAL_ROOTS_DIR = path.join(GLOBAL_GOTO_DIR, "roots")
LOCAL_ROOTS_DIR = path.join(LOCAL_GOTO_DIR, "roots")


###############################################################################
# Classes                                                                     #
###############################################################################


class ArgumentParserError(Exception):
    pass


class GenerousArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

    def parse_args(self, args=None, namespace=None):
        try:
            return super(GenerousArgumentParser, self).parse_args(args)
        except ArgumentParserError:
            return super(GenerousArgumentParser, self).parse_args([])


class Root(object):

    def __init__(
        self,
        root: str,
        path: str,
        defaults: List[str],
        shortcuts: Mapping[str, str],
        **extra  # Ignore any extraneous keywords
    ):
        self.root = root
        self.path = path
        self.defaults = defaults
        self.shortcuts = shortcuts

    @classmethod
    def empty(cls, root: str, config_filepath: str) -> "Root":
        root_obj = cls(
            root=root,
            path="",
            default=[],
            shortcuts=dict()
        )
        root_obj.config_filepath = config_filepath
        return root_obj

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"{self.__dict__.__str__()}"

    def json(self) -> str:
        return json.dumps(self.shortcuts, **json_args(True))

    @staticmethod
    def read(filepath) -> "Root":
        try:
            with open(filepath) as f:
                root = Root(**json.load(f))
                root.config_filepath = filepath
                return root
        except Exception:
            return None

    def write(self) -> None:
        with open(self.config_filepath, 'w') as f:
            json.dump(self, f, **json_args(True))


class Roots(object):

    def __init__(self, roots: Mapping[str, Root]):
        self._roots = roots

    def __str__(self) -> str:
        return self._roots.__str__()

    def __repr__(self) -> str:
        return self.__str__()

    def __getitem__(self, root):
        return self._roots.get(root, None)

    def __contains__(self, item):
        return self[item] is not None

    def roots(self) -> List[str]:
        return list(self._roots.keys())

    def keys(self) -> List[str]:
        return self.roots()

    def get(self, root, attr) -> Any:
        root_obj = self[root]
        if root_obj is None:
            return None
        return getattr(root_obj, attr, None)

    def name(self, root):
        return self.get(root, "name")

    def path(self, root):
        return self.get(root, "path")

    def json(self, root) -> str:
        jsoner = self.get(root, "json")
        if jsoner:
            return jsoner()

    def all_json(self, root) -> str:
        return json.dumps(self.all_shortcuts(root), **json_args(True))

    def all_shortcuts(self, root) -> Mapping[str, str]:
        root_obj = self[root]
        if root_obj is None:
            return {}

        cuts = root_obj.shortcuts
        for default in root_obj.defaults:
            cuts.update(self.all_shortcuts(default))
        return cuts

    def root_filepath(self, root):
        return self.get(root, "config_filepath")

    @staticmethod
    def read(*dirpaths: str) -> "Roots":
        files = []
        for dirpath in dirpaths:
            files += [
                path.join(dirpath, f)
                for f in os.listdir(dirpath)
                if path.isfile(path.join(dirpath, f))
            ]

        roots = {
            root.root: root for root in
            (Root.read(f) for f in files)
            if root is not None and root.root is not None
        }

        return Roots(roots)

    def write(self) -> None:
        for _, root_obj in self._roots.items():
            root_obj.write()


###############################################################################
# Helper functions                                                            #
###############################################################################

def json_args(use_dict: bool):
    return {
        "default": lambda o: o.__dict__ if use_dict else o,
        "sort_keys": True,
        "indent": "\t"
    }


def get_parser(parser_type):

    parser = parser_type(description=__doc__,
                         formatter_class=argparse.RawDescriptionHelpFormatter)

    group = parser.add_mutually_exclusive_group()

    group.add_argument("-s", "--set",
                       help="set the current root directory")

    group.add_argument("-p", "--print",
                       help="print available options",
                       dest="print_arg",
                       action="store_true")

    group.add_argument("-o", "--open",
                       help="open the info file for the root",
                       metavar="FILE")

    group.add_argument("-a", "--all",
                       help="see available shortcuts for a root",
                       action="store_true")

    group.add_argument("-r", "--roots",
                       help="list roots",
                       action="store_true")

    group.add_argument("-c", "--configs", "--config",
                       help="open config JSON",
                       action="store_true")

    group.add_argument("-n", "--new",
                       help="create new root",
                       metavar=("ROOT"),
                       nargs=1)

    group.add_argument("--setup",
                       help="create default config files",
                       action="store_true")

    group.add_argument("--complete",
                       help="complete cmd line")

    parser.add_argument("-g", "--use-global",
                        help="create new roots in the GLOBAL dir",
                        action="store_true")

    parser.add_argument("-t", "--temp-file",
                        help="temp file to write path to",
                        action="store")

    parser.add_argument("first", nargs='?', default="all")
    parser.add_argument("second", nargs='?')
    return parser


def parameters_from_args(args, configs):

    if args.second:
        root = args.first
        shortcut = args.second
    else:
        root = configs["current_root"]
        shortcut = args.first

    return (root, shortcut)


def set_current_root(new_root, roots, configs):

    current_root = roots.name(configs["current_root"])

    if new_root in roots:
        configs["current_root"] = new_root
        save_configs(configs)
        return f"New root set to {new_root}"
    else:
        return f"{new_root} not recognized, current root is stil {current_root}"


def save_configs(configs):
    with open(CONFIG_FILEPATH, 'w') as config_file:
        json.dump(configs, config_file, **json_args(False))


def load_file(filepath):
    with open(filepath) as the_file:
        return json.load(the_file)


def print_path(path, temp_file):
    if temp_file:
        with open(temp_file, 'w') as f:
            f.write(path)
    else:
        print(path)

def print_information(print_arg, roots, configs):

    if print_arg == "all":
        root_obj = roots[configs['current_root']]
        return root_obj.json()
    elif print_arg == "configs":
        return json.dumps(configs, **json_args(False))
    elif print_arg == "roots":
        return json.dumps(roots.keys(), **json_args(False))
    elif print_arg in roots:
        return roots.json(print_arg)
    else:
        return "Invalid print arg: {}".format(print_arg)


def all_print_information(print_arg, roots, configs):

    if print_arg == "all":
        return roots.all_json(configs["current_root"])
    elif print_arg == "roots":
        return json.dumps(roots.keys(), **json_args(False))
    elif print_arg in roots:
        return roots.all_json(print_arg)
    else:
        return f"Invalid print arg: {print_arg}"


def get_path(shortcut, roots, root):

    shortcuts = roots.all_shortcuts(root)
    relative_path = shortcuts.get(shortcut, None)

    if relative_path is None:
        return None

    full_path = path.join(roots.path(root), relative_path)
    return full_path


def edit_file(filepath):
    editor = os.getenv('VISUAL')
    return subprocess.call([editor, filepath])


def ensure_dir(directory):
    os.makedirs(directory, exist_ok=True)


def ensure_file(path):
    open(path, 'w').close()


def write_config_files():

    # ensure all directories and files are present
    ensure_dir(LOCAL_GOTO_DIR)
    ensure_dir(LOCAL_ROOTS_DIR)

    ensure_file(CONFIG_FILEPATH)

    # write configs
    configs = {"current_root": "goto"}
    save_configs(configs)


def find_applicable_complete_options(args, roots, configs):

    cmd = args.complete.split(' ')
    complete_args = get_parser(GenerousArgumentParser).parse_args(cmd)

    options = {}
    word_to_complete = ""

    if len(cmd) == 1:
        options = roots
        word_to_complete = ""
    elif len(cmd) > 1:
        if cmd[1] in ['-s', '--set'] and len(cmd) < 4:
            options = roots
            word_to_complete = complete_args.set if complete_args.set else ""
        elif cmd[1] in ['-o', '--open'] and len(cmd) < 4:
            options = roots
            word_to_complete = complete_args.open if complete_args.open else ""
        elif len(cmd) == 2:
            if cmd[1] in roots:
                options = roots.all_shortcuts(cmd[1])
                word_to_complete = ""
            else:
                options = roots.all_shortcuts(configs['current_root'])
                word_to_complete = cmd[1]
        elif len(cmd) == 3:
            if cmd[1] in roots:
                options = roots.all_shortcuts(cmd[1])
                word_to_complete = cmd[2]

    shortcuts = list(options.keys())
    return filter_applicable_shortcuts(shortcuts, word_to_complete)


def filter_applicable_shortcuts(shortcuts, word_to_complete):
    return [shortcut for shortcut in shortcuts if shortcut.startswith(word_to_complete)]


###############################################################################
# Main script                                                                 #
###############################################################################

def main():

    #
    # Parse command line arguments
    # # # # # # # # # # # # # # # # #

    parser = get_parser(argparse.ArgumentParser)
    args = parser.parse_args()

    # check setup mode
    if args.setup:
        if path.isdir(LOCAL_GOTO_DIR):
            print("aborting, configs already exist")
            sys.exit(1)
        else:
            write_config_files()
            print("wrote config files")
            sys.exit(0)

    #
    # Load configs
    # # # # # # # # # # # #

    configs = load_file(CONFIG_FILEPATH)
    roots = Roots.read(GLOBAL_ROOTS_DIR, LOCAL_ROOTS_DIR)

    #
    # Set op mode
    # # # # # # # # # # # #

    exit_code = 0

    # set current root mode
    if args.set:
        result_msg = set_current_root(args.set, roots, configs)
        print(result_msg)

    # print mode
    elif args.print_arg:
        information = print_information(args.first, roots, configs)
        print(information)

    # open mode
    elif args.open:
        root_filepath = roots.root_filepath(args.open)
        if path.isfile(root_filepath):
            edit_file(root_filepath)
            print("Opening file " + root_filepath)
        else:
            print("Error opening file: " + root_filepath)

    # edit configs mode
    elif args.configs:
        print("Editing configs")
        edit_file(CONFIG_FILEPATH)

    # print all mode
    elif args.all:
        all_shortcuts = all_print_information(args.first, roots, configs)
        print(all_shortcuts)

    # print roots mode
    elif args.roots:
        for root in roots.roots():
            if root == configs["current_root"]:
                print(f"*{root}")
            else:
                print(root)

    # create new root mode
    elif args.new:
        root = args.new[0]

        root_dir = GLOBAL_ROOTS_DIR if args.use_global else LOCAL_ROOTS_DIR
        new_root_filepath = path.join(root_dir, f"{root}.json")

        if not path.isfile(new_root_filepath):
            Root.empty(root, new_root_filepath).write()
            edit_file(new_root_filepath)
            print("Writing new root {}".format(root))
        else:
            print("ERROR! root {} already exists!".format(root))

    # complete mode
    elif args.complete:
        applicable_options = find_applicable_complete_options(args, roots, configs)
        print(applicable_options)

    # goto shortcut mode
    elif args.first:

        # combine cmdlines args + configs to get path params
        root, shortcut = parameters_from_args(args, configs)

        # expand shortcut into full length path
        full_path = get_path(shortcut, roots, root)

        # name of path to change to; print this so bash can cd to it
        if full_path:
            print_path(full_path, args.temp_file)

        # if shortcut not resolved, print error and exit
        else:
            print(f"Shortcut missing in {roots[root].root}")
            exit_code = 1

    # no mode selected, print help
    else:
        parser.print_help()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
