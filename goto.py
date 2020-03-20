#!/usr/bin/env python3

"""command line utility to navigate file structure using bookmarks

goto is a tool that allows you to quickly move between directories.
The basic workflow is as follows:

1. Use goto -n <root> to create a new root file
2. Edit the new json root file to configure the root
2. Use goto -s <root> to set the current root
3. Use goto <shortcut> to cd to the shortcut in the current root dir

All shortcuts are given relative to root dir.

File structures

setup/config.json: contains overall settings, e.g. the current root dir

roots/: contains all available roots, one per file.  Has information
on each including abbreviation and path. Add new files here to include
more root directories. Use the "defaults" field to add extra sets of
shortcuts to this root directory. This is useful if you have a number
of directories with similar file structure. For example, if you have
multiple branches of the same repo checked out.
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
from typing import Mapping, List

###############################################################################
# Constants                                                                   #
###############################################################################

GOTO_DIR = path.expanduser("~/.config/goto")

CONFIG_FILEPATH = path.join(GOTO_DIR, "config.json")
ROOTS_DIR = path.join(GOTO_DIR, "roots")


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

    def __init__(self, root: str, path: str, defaults: List[str], shortcuts: Mapping[str, str]):
        self.root = root
        self.path = path
        self.defaults = defaults
        self.shortcuts = shortcuts

    @classmethod
    def empty(cls, root="") -> "Root":
        return cls(root, "", [], dict())

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"{self.__dict__.__str__()}"

    def json(self) -> str:
        return json.dumps(self.shortcuts, **json_args(True))

    def all_json(self, roots) -> str:
        return json.dumps(self.all_shortcuts(roots), **json_args(True))

    def all_shortcuts(self, roots: List["Root"]) -> Mapping[str, str]:
        cuts = self.shortcuts
        for default in self.defaults:
            cuts.update(roots[default].shortcuts)
        return cuts

    @staticmethod
    def from_file(filepath) -> "Root":
        try: 
            with open(filepath) as f:
                return Root(**json.load(f))
        except:
            return None

    @staticmethod
    def from_dir(filepath) -> Mapping[str, "Root"]:
        files = [
            path.join(filepath, f)
            for f in os.listdir(filepath)
            if path.isfile(path.join(filepath, f))
        ]

        roots = {
                root.root: root for root in 
                    (Root.from_file(f) for f in files)
                if root is not None and root.root is not None
        }

        return roots

    def to_file(self, filepath: str) -> None:
        with open(filepath, 'w') as f:
                json.dump(self, f, **json_args(True))
 
    @staticmethod
    def to_dir(filepath, roots: List["Root"]) -> None:

        for root in roots:
            root_filename = f"{root.root}.json"
            root_filepath = path.join(filepath, root_filename)
            root.to_file(root_filepath)
           

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

    current_root=roots[configs["current_root"]].root

    if new_root in roots:
        configs["current_root"] = new_root
        save_configs(configs)
        return f"New root set to {roots[new_root].root}"
    else:
        return f"{new_root} not recognized, current root is stil {current_root}"


def save_configs(configs):
    with open(CONFIG_FILEPATH, 'w') as config_file:
        json.dump(configs, config_file, **json_args(False))


def load_file(filepath):
    with open(filepath) as the_file:
        return json.load(the_file)


def print_information(print_arg, roots, configs):

    if print_arg == "all":
        root_obj = roots[configs['current_root']]
        return root_obj.json()
    elif print_arg == "configs":
        return json.dumps(configs, **json_args(False))
    elif print_arg == "roots":
        return json.dumps(list(roots.keys()), **json_args(False))
    elif print_arg in roots:
        return roots[print_arg].json()
    else:
        return "Invalid print arg: {}".format(print_arg)


def all_print_information(print_arg, roots, configs):

    if print_arg == "all":
        return roots[configs["current_root"]].all_json(roots)
    elif print_arg == "roots":
        return json.dumps(list(roots.keys()), **json_args(False))
    elif print_arg in roots:
        return roots[print_arg].all_json(roots)
    else:
        return f"Invalid print arg: {print_arg}"


def get_path(shortcut, roots, root):

    root_obj = roots[root]
    shortcuts = root_obj.all_shortcuts(roots)
    
    relative_path = shortcuts.get(shortcut, None)

    if relative_path is None:
        return None

    full_path = path.join(root_obj.path, relative_path)
    return full_path


def get_root_filepath(root, roots):
    if root in roots:
        root_obj = roots[root]
        return path.join(ROOTS_DIR, f"{root_obj.root}.json")
    return None


def root_file_exists(filepath):
    return path.isfile(filepath)


def edit_file(filepath):
    editor = os.getenv('VISUAL')
    return subprocess.call([editor, filepath])


def ensure_dir(directory):
    os.makedirs(directory, exist_ok=True)


def ensure_file(path):
    open(path, 'w').close()


def write_config_files():

    # ensure all directories and files are present
    ensure_dir(GOTO_DIR)
    ensure_dir(ROOTS_DIR)

    ensure_file(CONFIG_FILEPATH)

    # write configs
    configs = {"current_root": "goto"}
    save_configs(configs)

    # write roots file
    roots = [
        Root(
            root="goto",
            path="~/.config/goto",
            defaults=[],
            shortcuts={
                "roots": "roots"
            }
        ),
    ]
    Root.to_dir(ROOTS_DIR, roots)
    

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
                options = roots[cmd[1]].all_shortcuts(roots)
                word_to_complete = ""
            else:
                options = roots[configs['current_root']].all_shortcuts(roots)
                word_to_complete = cmd[1]
        elif len(cmd) == 3:
            if cmd[1] in roots:
                options = roots[cmd[1]].all_shortcuts(roots)
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
        print("press 'y' to confirm config overwrite:\n", flush=True)
        ans = input()
        if ans == 'y':
            write_config_files()
            print("wrote config files")
        else:
            print("aborting")
        sys.exit(0)

    #
    # Load configs
    # # # # # # # # # # # #

    configs = load_file(CONFIG_FILEPATH)
    roots = Root.from_dir(ROOTS_DIR)

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
        root_filepath = get_root_filepath(args.open, roots)
        if root_file_exists(root_filepath):
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

    # create new root mode
    elif args.new:
        root = args.new[0]
        new_root_filepath = path.join(ROOTS_DIR, f"{root}.json")

        if not root_file_exists(new_root_filepath):
            Root.empty(root).to_file(new_root_filepath)
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
            print(full_path)

        # if shortcut not resolved, print error and exit
        else:
            print(f"Shortcut not found in {roots[root].root}")
            exit_code = 1

    # no mode selected, print help
    else:
        parser.print_help()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
