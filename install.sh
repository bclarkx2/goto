#!/usr/bin/env sh

source_dir="$(realpath $(dirname 0))"
source_script="$source_dir/goto"
source_py="$source_dir/goto.py"

install_dir="${1:-$HOME/.local/bin}"
install_script="$install_dir/goto"
install_py="$install_dir/goto.py"

# Make symlink to executable
if [ -f "$source_script" ] && [ -f "$source_py" ]; then
	
	# Ensure dir exists
 	mkdir -p "$install_dir"

  # Create symlinks
	ln -s "$source_script" "$install_script"
	ln -s "$source_py" "$install_py"

  # Call setup function
  "$install_script" --setup

else
	echo "Ensure goto and goto.py exist in this directory" 1>&2
fi

