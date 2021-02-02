# elf-plotter

This is a simple python tool to plot the bytes of a file in the
[Executable and Linkable Format (ELF)](https://man7.org/linux/man-pages/man5/elf.5.html)
and colorize the headers, e.g. the
* ELF Header (`Ehdr`),
* Program Header (`Phdr`), and
* Section header (`Shdr`),

and sections, e.g.

* `.text`,
* `.data`,
* …,

in different colors. The brightness of the pixels is their byte-value, e.g. if `.text` gets the color red in the legend, a pixel with the color `#ff0000` will be `0xff`, and `#000000` will be `0x00`.

The subplot title is the name of the file, and the file's `.comment` section which conveniently contains some compiler information (at least for `gcc` and `clang`).

## Dependencies:

* [pyelftools](https://github.com/eliben/pyelftools)

## Installation:

```bash
$ git clone https://github.com/felsenhower/elf-plotter
$ cd elf-plotter
$ pip install -r requirements.txt
```

## Usage:

Simply call `plot-elf.py` with a list of ELF files,
e.g. exexutables or .o files

```bash
$ plot-elf.py "/path/to/elffile.o"
```
