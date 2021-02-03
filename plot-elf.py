#!/usr/bin/env python3


# https://github.com/eliben/pyelftools/wiki/User's-guide
# https://man7.org/linux/man-pages/man5/elf.5.html
# https://en.wikipedia.org/wiki/Executable_and_Linkable_Format


import numpy as np
import math
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.lines import Line2D
import sys
import io
import os.path
import re
import hashlib
from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
import typing
from typing import List, Dict, Tuple, Any, Collection, Set


# Workaround because numpy and the typing system don't work very well together atm...
NpArray = Any


class PlottingOptions:
    selected_parts: Set[str] = set()
    strip: bool = False


class ElfFileData:
    byte_data: NpArray = None
    elf_data: ELFFile = None


def error(msg: str) -> None:
    """
    Print a message and quit with non-zero exit code.
    :param msg: "Error: " + the message to print.
    """
    print("Error: {}".format(msg))
    sys.exit(1)


def load_elf_files(filenames: Collection[str]) -> Dict[str,ElfFileData]:
    """
    Load the ELF files and read their ELF data and byte data.
    :param filenames: The names of the files to load.
    :return: A dict from filename to ElfFileData objects, which contain the
             ELF data and byte data.
    """
    result: Dict[str,ElfFileData] = dict()
    for f in filenames:
        with open (f, "rb") as elffile:
            raw_data = elffile.read()
        try:
            result[f] = ElfFileData()
            result[f].byte_data = np.frombuffer(raw_data, dtype="uint8")
            result[f].elf_data = ELFFile(io.BytesIO(raw_data))
        except ELFError:
            error("Not a valid ELF file: \"{}\"".format(f))
    return result


def get_max_length(arrays: Collection[Collection]) -> int:
    """
    Get the maximum length of the supplied collections.
    :param arrays: The collections to analyze.
    :return: The maximum length.
    """
    max_length: int = 0
    for a in arrays:
        size: int = len(a)
        if size > max_length:
            max_length = size
    return max_length


def pad_array(array: NpArray, length: int) -> NpArray:
    """
    Pad the given array to the given length.
    :param array: The array to pad.
    :param length: The length to pad the array to.
    :return: The padded array.
    """
    result: NpArray = np.zeros((length,3), dtype=array.dtype)
    result[:len(array)] = array
    return result


def filter_parts(parts: List[str], selected_parts: Collection[str]) -> List[str]:
    """
    Filter the given parts with the filter list supplied.
    :param parts: The input list.
    :param selected_parts: A set of strings that may be equal to parts (headers /
                           sections) to keep or may be a regex enclose in
                           slashes ("/regex/").
    :return: The filtered list. If selected parts is empty, everything will be kept.
    """
    if len(selected_parts) == 0:
        return parts
    result: List[str] = []
    for (name,offset,length) in parts:
        for filter in selected_parts:
            if filter.startswith("/") and filter.endswith("/"):
                if re.match(filter[1:-1], name):
                    result.append((name,offset,length))
            else:
                if filter == name:
                    result.append((name,offset,length))
    return result


def get_parts(elf_files: Dict[str,ElfFileData], options: Dict[str,PlottingOptions]) -> Dict[str,List[str]]:
    """
    Get a list of parts for all input files.
    :param elf_files: A dict from filename to ElfFileData objects that contains
                      the ELF and byte data.
    :param options: A dict from filename to PlottingOptions objects which
                    determine selected sections and stripping.
    :return: A dict from filename to lists of parts.
    """
    result = dict()
    for f in elf_files:
        elf: ELFFile = elf_files[f].elf_data
        selected_parts: Set[str] = options[f].selected_parts
        part_names = ["Ehdr"]
        part_offsets = [0]
        part_lengths = [elf.header.e_ehsize]
        for s in elf.iter_sections():
            part_names.append(s.name)
            part_offsets.append(part_offsets[-1] + part_lengths[-1])
            part_lengths.append(s.data_size)
        part_names.extend(["Phdr", "Shdr"])
        part_offsets.extend([elf.header.e_phoff, elf.header.e_shoff])
        part_lengths.extend([elf.header.e_phentsize, elf.header.e_shentsize])
        parts = list(zip(part_names, part_offsets, part_lengths))
        parts = [(name,offset,length) for (name,offset,length) in parts if length > 0]
        parts = filter_parts(parts, selected_parts)
        if len(parts) == 0:
            error("No parts in \"{}\" match selection {}".format(f,selected_parts))
        result[f] = parts
    return result


num_colors = 3600
colors = cm.rainbow(np.linspace(0, 1, num_colors))
colors = colors[:,0:3]
saved_colors = dict()

def get_color(text: str) -> NpArray:
    """
    Get a color for the given text that will always be the same.
    :param text: The input text.
    :return: A color as RGB value.
    """
    if text in saved_colors:
        color = saved_colors[text]
    else:
        color = colors[int(hashlib.md5(text.encode()).hexdigest(), 16) % num_colors]
        saved_colors[text] = color
    return color



def colorize_data(elf_files: Dict[str,ElfFileData], parts: Dict[str,List[str]]) -> Dict[str,List[Tuple[str,Line2D]]]:
    """
    Colorize the ELF header, Program Header, Section Header, and various sections
    (e.g. .text, .date, …) of the given bytes of the ELF Object Code Files with
    different colors on the HSV spectrum and prepare a legend for the plot.
    :param elf_files: A dict from filename to ElfFileData objects that contains
                      the ELF and byte data.
    :param parts: A dict from filename to parts to keep.
    :return: A dict from filename to the names of the parts of the data and to
             the Line2D objects containing the colors of the parts of the data.
    """
    legend_data: Dict[str,List[Tuple[str,Line2D]]] = dict()
    for f in elf_files:
        bytes: NpArray = elf_files[f].byte_data
        bytes = np.stack((bytes,bytes,bytes), axis=1)
        current_parts = parts[f]
        current_legend_data = []
        for name, offset, length in current_parts:
            color = get_color(name)
            bytes[offset : offset+length] = (bytes[offset : offset+length] * color).astype("uint8")
            current_legend_data.append((name, Line2D([0], [0], color=color, lw=4)))
        legend_data[f] = current_legend_data
        elf_files[f].byte_data = bytes
    return legend_data


def strip_data(elf_files: Dict[str,ElfFileData], parts: Dict[str,List[str]], options: Dict[str,PlottingOptions]) -> None:
    """
    If specified in options, strip away all the parts we don't want to highlight.
    :param elf_files: A dict from filename to ElfFileData objects that contains
                      the ELF and byte data.
    :param parts: A dict from filename to parts to keep.
    :param options: A dict from filename to PlottingOptions objects which
                    determine selected sections and stripping.
    """
    for f in elf_files:
        current_parts = parts[f]
        bytes: NpArray = elf_files[f].byte_data
        strip: bool = options[f].strip
        if strip:
            stripped_bytes = np.empty((0,3), dtype="uint8")
            for i, (name, offset, length) in enumerate(current_parts):
                stripped_bytes = np.append(stripped_bytes, bytes[offset : offset+length], axis=0)
            bytes = stripped_bytes
        elf_files[f].byte_data = bytes


def plot_elf_files(elf_files: Dict[str,ElfFileData], legend_data: Dict[str,List[Tuple[str,Line2D]]]) -> None:
    """
    Plot the given ELF files.
    :param elf_files: A dict from filename to ElfFileData objects that contains
                      the ELF and byte data.
    :param legend_data: A dict from filename to the names of the parts of the
                        data and to the Line2D objects containing the colors of
                        the parts of the data.

    """
    num_plots = len(elf_files)
    fig, ax = plt.subplots(ncols=num_plots)
    for i, f in enumerate(elf_files):
        colorized_bytes = elf_files[f].byte_data
        elf = elf_files[f].elf_data
        cax = ax[i] if num_plots > 1 else ax
        sqrt_len = int(math.sqrt(len(colorized_bytes)))
        w = int(sqrt_len / math.sqrt(2) / 8) * 8
        h = int(len(colorized_bytes) / w)
        colorized_bytes = colorized_bytes[:(w*h)]
        colorized_bytes = colorized_bytes.reshape(h,w,3)
        cax.imshow(colorized_bytes)
        compiler = elf.get_section_by_name(".comment").data().decode("utf-8").strip('\x00')
        cax.set_title("{}\n[{}]".format(f, compiler))
        cax.legend([x[1] for x in legend_data[f]], [x[0] for x in legend_data[f]], loc=(1.04,0))
    mng = fig.canvas.manager
    mng.window.showMaximized()
    plt.show()


def parse_args() -> Dict[str,PlottingOptions]:
    """
    Parse the arguments.
    :return: A dict from filename to PlottingOptions objects which
             determine selected sections and stripping.
    """
    args: List[str] = sys.argv[1:]
    if args == []:
        error("No filenames given.")
    result: Dict[str,PlottingOptions] = {}
    current_filename: str = ""
    global_strip: bool = False
    global_selected_parts: Set[str] = set()
    for arg in args:
        if arg.startswith("+"):
            try:
                if arg.startswith("++"):
                    current_selected_parts = arg[2:].split(",")
                    current_strip = True
                else:
                    current_selected_parts = arg[1:].split(",")
                    current_strip = False
                if current_filename == "":
                    global_selected_parts.update(set(current_selected_parts))
                    global_strip |= current_strip
                else:
                    result[current_filename].selected_parts.update(set(current_selected_parts))
                    result[current_filename].strip |= current_strip
            except:
                error("Could not parse the list \"{}\"".format(arg))
        elif os.path.isfile(arg):
            if arg in result:
                error("Specified filename twice: \"{}\"".format(arg))
            current_filename = arg
            result[current_filename] = PlottingOptions()
        else:
            error("Not a valid file: \"{}\"".format(arg))
    if len(global_selected_parts) != 0:
        for filename in result:
            result[filename].selected_parts.update(set(global_selected_parts))
            result[filename].strip |= global_strip
    return result


def main() -> None:
    options = parse_args()
    filenames = options.keys()

    # Load the object code files as bytes and ELF data
    elf_files = load_elf_files(filenames)

    # Get the parts of the file and filter them
    parts = get_parts(elf_files, options)

    # Colorize the data so that the ELF header, .text, .data, … all have
    # different colors.
    legend_data = colorize_data(elf_files, parts)

    # If necessary, strip away unwanted bytes
    strip_data(elf_files, parts, options)

    # Get the maximum length and pad each array to this value
    max_length = get_max_length([e.byte_data for e in elf_files.values()])
    for f in filenames:
        elf_files[f].byte_data = pad_array(elf_files[f].byte_data, max_length)

    # Plot the arrays.
    plot_elf_files(elf_files, legend_data)


if __name__ == '__main__':
    main()
