#!/usr/bin/env python3

"""command line utility to navigate file structure using bookmarks

goto is a tool that allows you to quickly move between directories.
The basic workflow is as follows:

1. Edit the ~/.config/goto/info JSON files to set up the shortcuts you want
2. Use goto -s <root> to set the current root
3. Use goto <shortcut> to cd to the shortcut in the current root dir

All shortcuts are given relative to root dir.

File structures

setup/config.json: contains overall settings, e.g. the current root dir

setup/roots.json: contains list of all available root directories. Has
information on each including abbreviation, name, and path. Edit
this file to include more root directories. Use the "defaults" field to
add extra sets of shortcuts to this root directory. This is useful if
you have a number of directories with similar file structure. For example,
if you have multiple branches of the same repo checked out.

info/onx_defaults.json: this file contains a variety of common shortcut
paths. These can be accessed in any root dir.
"""

###############################################################################
# Imports                                                                     #
###############################################################################

import os
import argparse
import json
import sys
import subprocess

from json import JSONEncoder
from os import path

from typing import Mapping, List

###############################################################################
# Constants                                                                   #
###############################################################################

GOTO_DIR = os.path.expanduser("~/.config/goto")

CONFIG_FILEPATH = os.path.join(GOTO_DIR, "config.json")
ROOTS_DIR = os.path.join(GOTO_DIR, "roots")

PRINT_ARGS = ["configs", "roots"]


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
            name: str,
            path: str,
            defaults: List[str],
            shortcuts: List[str]):
        self.root = root
        self.name = name
        self.path = path
        self.defaults = defaults
        self.shortcuts = shortcuts


    def __repr__(self) -> str:
        return self.__str__()


    def __str__(self) -> str:
        return f"{self.__dict__.__str__()}"
       

    def json(self) -> str:
        return json.dumps(
            self.shortcuts,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent="\t"
        )


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

    @staticmethod
    def to_dir(filepath, roots: List["Root"]) -> None:

        for root in roots:
            root_filename = f"{root.root}.json"
            root_filepath = path.join(filepath, root_filename)

            with open(root_filepath, 'w') as root_file:
                json.dump(root, root_file, default=lambda o: o.__dict__, sort_keys=True, indent="\t")


###############################################################################
# Helper functions                                                            #
###############################################################################

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
                       help="open list of roots",
                       action="store_true")

    group.add_argument("-c", "--configs", "--config",
                       help="open config JSON",
                       action="store_true")

    group.add_argument("-n", "--new",
                       help="create new root",
                       metavar=("SHORTCUT", "NAME"),
                       nargs=2)

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


def get_info(root_name):

    info_filepath = os.path.join(ROOTS_DIR, root_name) + ".json"

    try:
        with open(info_filepath) as info_file:
            info = json.load(info_file)
    except OSError:
        info = {}

    return info


def set_relative_path(shortcut, shortcuts):

    for shortcut_set in shortcuts:
        if shortcut in shortcut_set:
            return shortcut_set[shortcut]

    return None


def set_current_root(new_root, roots, configs):

    current_root=roots[configs["current_root"]].name

    if new_root in roots:
        configs["current_root"] = new_root
        save_configs(configs)
        return f"New root set to {roots[new_root].name}"
    else:
        return f"{new_root} not recognized, current root is stil {current_root}"


def save_configs(configs):
    with open(CONFIG_FILEPATH, 'w') as config_file:
        json.dump(configs, config_file, sort_keys=True, indent=4)


def load_file(filepath):
    with open(filepath) as the_file:
        return json.load(the_file)


def print_information(print_arg, roots, configs):

    if print_arg == "all":
        root_obj = roots[configs['current_root']]
        return root_obj.json()
    elif print_arg == "configs":
        return json.dumps(configs, sort_keys=True, indent="\t")
    elif print_arg == "roots":
        return json.dumps(list(roots.keys()), sort_keys=True, indent="\t")
    elif print_arg in roots:
        return roots[print_arg].json()
    else:
        return "Invalid print arg: {}".format(print_arg)


def all_information_dict(print_arg, roots, configs):
    if print_arg == "all":
        print_arg = configs['current_root']

    root_obj = roots[print_arg]

    shortcuts = get_info(root_obj['name'])

    for default in root_obj['defaults']:
        shortcuts.update(get_info(default))

    return shortcuts


def all_print_information(print_arg, roots, configs):

    shortcuts = all_information_dict(print_arg, roots, configs)
    return json.dumps(shortcuts, sort_keys=True, indent=4)


def get_printables(roots):
    '''list the things that can be printed

    Roots should display as root names (ad, ot, etc...), while defaults
    should display as names (onx_defaults, etc...)
    '''

    all_root_names = {roots[root]['name'] for root in roots}

    all_non_root_names = all_names_in_info_dir - all_root_names

    all_roots = set(roots.keys())

    all_printables = all_non_root_names | all_roots

    return list(all_printables)


def get_shortcuts(shortcut, roots, root):

    info_sources = []

    # always add root info
    root_obj = roots[root]
    info_sources.append(root_obj.shortcuts)

    # add any defaults this root is set up to use
    for default_root in root_obj.defaults:
        default_root_obj = roots[default_root]
        info_sources.append(default_root_obj.bookmarks)

    return info_sources

def get_path(shortcut, roots, root):

    shortcuts = get_shortcuts(shortcut, roots, root)
    
    relative_path = set_relative_path(shortcut, shortcuts)

    if relative_path is None:
        return None

    root_obj = roots[root]
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


def write_blank_info_file(new_root_filepath):
    with open(new_root_filepath, 'w') as new_root_file:
        json.dump({}, new_root_file, sort_keys=True, indent=4)


def add_empty_root_to_roots_file(shortcut, name, args, roots):
    roots[shortcut] = {
        "path": args.first if args.first else "",
        "name": name,
        "defaults": []
    }
    with open(ROOTS_FILEPATH, 'w') as roots_file:
        json.dump(roots, roots_file, sort_keys=True, indent=4)


def filter_applicable_shortcuts(shortcuts, word_to_complete):
    return [shortcut for shortcut in shortcuts if shortcut.startswith(word_to_complete)]


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
            root="com",
            name="common",
            path="",
            defaults=[],
            shortcuts={
                "root": "",
                "/": "",
            }
        ),
        Root(
            root="goto",
            name="goto",
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

    if len(cmd) == 1:
        options = roots
        word_to_complete = ""
    elif len(cmd) > 1:
        if cmd[1] in ['-s', '--set']:
            options = roots
            word_to_complete = complete_args.set if complete_args.set else ""
        elif cmd[1] in ['-o', '--open']:
            options = roots
            word_to_complete = complete_args.open if complete_args.open else ""
        elif len(cmd) == 2:
            if cmd[1] in roots:
                options = all_information_dict(cmd[1], roots)
                word_to_complete = ""
            else:
                options = all_information_dict(configs['current_root'], roots)
                word_to_complete = cmd[1]
        elif len(cmd) == 3:
            options = all_information_dict(cmd[1], roots)
            word_to_complete = cmd[2]
    else:
        options = {}
        word_to_complete = ""

    shortcuts = list(options.keys())
    return filter_applicable_shortcuts(shortcuts, word_to_complete)


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

    # edit roots mode
    elif args.roots:
        print("Editing roots")
        edit_file(ROOTS_FILEPATH)

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

        shortcut, name = args.new[0], args.new[1]

        new_root_filepath = os.path.join(ROOTS_DIR, name + ".json")

        if not root_file_exists(new_root_filepath):
            write_blank_info_file(new_root_filepath)
            add_empty_root_to_roots_file(shortcut, name, args, roots)
            edit_file(new_root_filepath)
            edit_file(ROOTS_FILEPATH)
            print("Writing new root {}".format(name))
        else:
            print("ERROR! root {} already exists!".format(name))

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
            print("Shortcut not found in {}".format(roots[root]["name"]))
            exit_code = 1

    # no mode selected, print help
    else:
        parser.print_help()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
