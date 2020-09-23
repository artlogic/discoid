import logging

from .diskio import DiskIO

LOG = logging.getLogger(__name__)

TOKENS = {
    0x80: "END",
    0x81: "FOR",
    0x82: "NEXT",
    0x83: "DATA",
    0x84: "INPUT",
    0x85: "DEL",
    0x86: "DIM",
    0x87: "READ",
    0x88: "GR",
    0x89: "TEXT",
    0x8A: "PR#",
    0x8B: "IN#",
    0x8C: "CALL",
    0x8D: "PLOT",
    0x8E: "HLIN",
    0x8F: "VLIN",
    0x90: "HGR2",
    0x91: "HGR",
    0x92: "HCOLOR=",
    0x93: "HPLOT",
    0x94: "DRAW",
    0x95: "XDRAW",
    0x96: "HTAB",
    0x97: "HOME",
    0x98: "ROT=",
    0x99: "SCALE=",
    0x9A: "SHLOAD",
    0x9B: "TRACE",
    0x9C: "NOTRACE",
    0x9D: "NORMAL",
    0x9E: "INVERSE",
    0x9F: "FLASH",
    0xA0: "COLOR=",
    0xA1: "POP",
    0xA2: "VTAB",
    0xA3: "HIMEM:",
    0xA4: "LOMEM:",
    0xA5: "ONERR",
    0xA6: "RESUME",
    0xA7: "RECALL",
    0xA8: "STORE",
    0xA9: "SPEED=",
    0xAA: "LET",
    0xAB: "GOTO",
    0xAC: "RUN",
    0xAD: "IF",
    0xAE: "RESTORE",
    0xAF: "&",
    0xB0: "GOSUB",
    0xB1: "RETURN",
    0xB2: "REM",
    0xB3: "STOP",
    0xB4: "ON",
    0xB5: "WAIT",
    0xB6: "LOAD",
    0xB7: "SAVE",
    0xB8: "DEF",
    0xB9: "POKE",
    0xBA: "PRINT",
    0xBB: "CONT",
    0xBC: "LIST",
    0xBD: "CLEAR",
    0xBE: "GET",
    0xBF: "NEW",
    0xC0: "TAB(",
    0xC1: "TO",
    0xC2: "FN",
    0xC3: "SPC(",
    0xC4: "THEN",
    0xC5: "AT",
    0xC6: "NOT",
    0xC7: "STEP",
    0xC8: "+",
    0xC9: "-",
    0xCA: "*",
    0xCB: "/",
    0xCC: "^",
    0xCD: "AND",
    0xCE: "OR",
    0xCF: ">",
    0xD0: "=",
    0xD1: "<",
    0xD2: "SGN",
    0xD3: "INT",
    0xD4: "ABS",
    0xD5: "USR",
    0xD6: "FRE",
    0xD7: "SCRN(",
    0xD8: "PDL",
    0xD9: "POS",
    0xDA: "SQR",
    0xDB: "RND",
    0xDC: "LOG",
    0xDD: "EXP",
    0xDE: "COS",
    0xDF: "SIN",
    0xE0: "TAN",
    0xE1: "ATN",
    0xE2: "PEEK",
    0xE3: "LEN",
    0xE4: "STR$",
    0xE5: "VAL",
    0xE6: "ASC",
    0xE7: "CHR$",
    0xE8: "LEFT$",
    0xE9: "RIGHT$",
    0xEA: "MID$",
}

# taking some time to look at the applesoft loading routines and it
# looks like the pointers get rewritten on load, meaning that the
# pointer might actually be wrong on disk - I'm seeing how it does it
# now, but we'll need to do the same...
#
# 1. skip past the first pointer and line number to the second byte of
# content (assume there's at least one token)
#
# 2. scan for 0 bytes (line terminators) until we find one (there's a
# edge case here, the counter rolls over when it hits 256, so really
# we can only have 252 bytes per line - you might be able to do some
# weird stuff by feeding the fix links routine something it doesn't
# expect...)
#
# 3. Once we find a zero byte, then rewrite the pointer to point at
# the right place
#
# Literally this is a whole scan for line terminators routine. The
# pointers are ignored, and I think this means we should ignore them.

# Some other points
#
# - sometimes there's extra junk after the 0000 next line pointer
# - ciderpress works roughly the same way as above
# - we can determine the base by scanning for the end of the first
#   line and subtracting the length from the first pointer - normally
#   it would be 0x801


def calculate_base(data):
    LOG.debug("Calulating base address.")
    next_line_pos = data.read_word()

    if next_line_pos == 0:
        # we've been given an empty file (probably) - assign an
        # arbitrary base
        return 0

    data.read_word()  # read the line number and ignore it
    data.read_until_null()  # read the first line and ignore it

    base = next_line_pos - data.tell()
    data.seek(0)  # reset the position pointer to 0

    LOG.debug("Base address is %d", base)
    return base


def get_next_line(data, base):
    LOG.debug("Processing next line.")
    next_line_pos = data.read_word()
    LOG.debug("Next line position: %d.", next_line_pos)

    if next_line_pos == 0:
        # This indicates end of program
        tail = data.read()  # get everything after the end
        if len(tail) > 1:
            # sometimes there's one garbage byte, but if there's more warn
            LOG.warning("Progam ended with %d unparsed bytes: %r", len(tail), tail)
        return None

    line_number = data.read_word()
    LOG.debug("Reading line %d.", line_number)
    line = data.read_until_null()

    if next_line_pos != base + data.tell():
        LOG.warning(
            "Expected next line at %d, but current position is %d.",
            next_line_pos,
            base + data.tell(),
        )

    return (line_number, line)


def detokenize(line):
    detokenized = ""

    for token in line:
        if token < 128:
            # ASCII byte
            if token == 13:
                detokenized += "\n"
            elif token == 7:
                detokenized += "<BELL>"
            elif token == 4:
                detokenized += "<CTRL-D>"
            else:
                if token < 32:
                    LOG.info("Found non-printable character, %d.", token)

                detokenized += chr(token)
        else:
            # token
            try:
                detokenized += " " + TOKENS[token] + " "
            except KeyError:
                # this means the program is corrupted - bail
                raise KeyError(f"Found invalid token {token}.")

    return detokenized


def parse(raw_data):
    data = DiskIO(raw_data)
    base = calculate_base(data)
    lines = []
    previous_line_number = -1  # no negative line numbers in Applesoft

    line = get_next_line(data, base)
    while line:
        # check for line number mischief
        line_number = line[0]
        if line_number <= previous_line_number:
            raise IndexError(
                f"Found equal/decreasing line number {line_number} after line {previous_line_number}"
            )

        # detokenize the line and save it
        lines.append((line_number, detokenize(line[1])))

        previous_line_number = line_number
        line = get_next_line(data, base)

    return lines
