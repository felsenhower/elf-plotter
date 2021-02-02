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
from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
import typing
from typing import List, Dict, Tuple, Any, Collection


# Workaround because numpy and the typing system don't work very well together atm...
NpArray = Any


def load_elf_files(filenames: Collection[str]) -> Tuple[Dict[str,NpArray],Dict[str,ELFFile]]:
    """
    Load the ELF files and read their ELF data and byte data.
    :param filenames: The names of the files to load.
    :return: A dict from filename to the bytes as numpy arrays with dtype "uint8",
             and a dict from filename to the ELF data.
    """
    data = dict()
    elf = dict()
    for f in filenames:
        with open (f, "rb") as elffile:
            raw_data = elffile.read()
        try:
            data[f] = np.frombuffer(raw_data, dtype="uint8")
            elf[f] = ELFFile(io.BytesIO(raw_data))
        except ELFError:
            print("Error: Not a valid ELF file: \"{}\"".format(f))
            sys.exit(1)
    return data, elf


def get_max_length(arrays: Collection[Collection]) -> int:
    """
    Get the maximum length of the supplied collections.
    :param arrays: The collections to analyze.
    :return: The maximum length.
    """
    max_length = 0
    for a in arrays:
        size = len(a)
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
    result = np.zeros(length, dtype=array.dtype)
    result[:len(array)] = array
    return result


def primes(n: int) -> List[int]:
    """
    Get the prime factorization of the given number
    :param n: The number.
    :return: The prime factorization as a list with repeated factors.
    """
    primfac = []
    d = 2
    while d*d <= n:
        while (n % d) == 0:
            primfac.append(d)
            n //= d
        d += 1
    if n > 1:
       primfac.append(n)
    return primfac


def get_optimal_color_division(num_colors: int) -> int:
    """
    For a list of equidistant colors on a continuous spectrum (e.g. hsv or
    rainbow), get a step width which with to select colors that is approximately
    1/3 of the number of colors, so that two adjacent colors are probably
    distinguishable, and which is selected so that the colors are never repeating.
    :param num_colors: The number of colors.
    :return: The step width with which to go through the list of colors.
    """
    division = int((num_colors - 1) / 3)
    while (division < num_colors):
        if not set(primes(division)).issubset(set(primes(num_colors))):
            return division
    return num_colors - 1


def colorize_data(data: Dict[str,NpArray], elf: Dict[str,NpArray]) -> Tuple[Dict[str,NpArray],Dict[str,List[str]],Dict[str,Line2D]]:
    """
    Colorize the ELF header, Program Header, Section Header, and various sections
    (e.g. .text, .date, …) of the given bytes of the ELF Object Code Files with
    different colors on the HSV spectrum and prepeare a legend for the plot.
    :param data: A dict from filename to the bytes as numpy arrays with dtype "uint8".
    :param elf: A dict from filename to the corresponding ELF data of the files.
    :return: A dict from filename to the colorized (RGB) data,
             a dict from filename to the names of the parts of the data,
             and a dict from filename to the Line2D objects containing the
             colors of the parts of the data.
    """
    res_data = dict()
    legend_names = dict()
    legend_colors = dict()
    for f in data.keys():
        curr_elf = elf[f]
        curr_data = data[f]
        curr_data = np.stack((curr_data,curr_data,curr_data), axis=1)

        part_names = ["Ehdr"]
        part_offsets = [0]
        part_lengths = [curr_elf.header.e_ehsize]
        for s in curr_elf.iter_sections():
            part_names.append(s.name)
            part_offsets.append(part_offsets[-1] + part_lengths[-1])
            part_lengths.append(s.data_size)
        part_names.extend(["Phdr", "Shdr"])
        part_offsets.extend([curr_elf.header.e_phoff, curr_elf.header.e_shoff])
        part_lengths.extend([curr_elf.header.e_phentsize, curr_elf.header.e_shentsize])

        parts = list(zip(part_names, part_offsets, part_lengths))
        parts = [(name,offset,length) for (name,offset,length) in parts if length > 0]
        num_parts = len(parts)

        colors = cm.rainbow(np.linspace(0, 1, num_parts))
        colors = colors[:,0:3]

        curr_legend_names = []
        curr_legend_colors = []
        color_division = get_optimal_color_division(num_parts)
        for i, (name, offset, length) in enumerate(parts):
            j = (i * color_division) % (num_parts)
            curr_data[offset : offset+length] = (curr_data[offset : offset+length] * colors[j]).astype("uint8")
            curr_legend_colors.append(Line2D([0], [0], color=colors[j], lw=4))
            curr_legend_names.append(name)
        res_data[f] = curr_data
        legend_names[f] = curr_legend_names
        legend_colors[f] = curr_legend_colors
    return res_data, legend_names, legend_colors


def plot_elf_files(data: Dict[str,NpArray], elf: Dict[str,ELFFile], legend_names: Dict[str,List[str]], legend_colors: Dict[str,Line2D]) -> None:
    """
    Plot the given ELF files.
    :param data: A dict from filename to colorized data of the files.
    :param elf: A dict from filename to the corresponding ELF data.
    :param legend_names: A dict from filename to the names of the parts of the file.
    :param legend_colors: A dict from filename to Line2D objects with colors of
                          the parts of the file.
    """
    num_plots = len(data)
    fig, ax = plt.subplots(ncols=num_plots)
    for i, f in enumerate(data):
        cax = ax[i] if num_plots > 1 else ax
        colorized_data = data[f]
        sqrt_len = int(math.sqrt(len(colorized_data)))
        w = int(sqrt_len / math.sqrt(2) / 8) * 8
        h = int(len(colorized_data) / w)
        colorized_data = colorized_data[:(w*h)]
        colorized_data = colorized_data.reshape(h,w,3)
        cax.imshow(colorized_data)
        compiler = elf[f].get_section_by_name(".comment").data().decode("utf-8").strip('\x00')
        cax.set_title("{} – {}".format(f, compiler))
        cax.legend(legend_colors[f], legend_names[f], loc=(1.04,0))
    mng = fig.canvas.manager
    mng.window.showMaximized()
    plt.show()


def main() -> None:

    filenames = sys.argv[1:]
    if filenames == []:
        print("Error: No filenames given.")
        sys.exit(1)
    for filename in filenames:
        if not os.path.isfile(filename):
            print("Error: Not a valid file: \"{}\"".format(filename))
            sys.exit(1)

    # Load the object code files as bytes and ELF data
    data, elf = load_elf_files(filenames)

    # Get the maximum length and pad each array to this value
    max_length = get_max_length(data.values())
    for f in filenames:
        data[f] = pad_array(data[f], max_length)

    # Colorize the data so that the ELF header, .text, .data, … all have
    # different colors.
    data, legend_names, legend_colors = colorize_data(data, elf)

    # Plot the arrays.
    plot_elf_files(data, elf, legend_names, legend_colors)


if __name__ == '__main__':
    main()
