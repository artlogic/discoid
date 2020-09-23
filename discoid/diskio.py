from io import BytesIO


class DiskIO(BytesIO):
    def read(self, size=-1):
        value = super().read(size)

        if size != -1 and len(value) < size:
            raise EOFError(
                f"Tried to read {size} bytes, but got {len(value)} bytes instead"
            )

        return value

    def read_byte(self):
        byte = self.read(1)
        return byte[0]

    def read_loc(self):
        loc = self.read(2)
        return tuple(loc)

    def read_word(self):
        word = self.read(2)
        return word[0] + word[1] * 256

    def read_until_null(self):
        line = b""

        byte = self.read(1)
        while byte != b"\0":
            line += byte
            byte = self.read(1)

        return line

    def skip(self, size):
        self.read(size)
