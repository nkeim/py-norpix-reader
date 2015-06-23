"""Reader for Norpix .seq files

Copyright 2013 by Nathan Keim

The SeqFile class is the interface to nearly all of this module's functionality.

Additionally, ts2dt() may be used to decode the timestamps returned by the SeqFile class.
"""
import os, struct, itertools
import datetime
from UserDict import UserDict
import numpy as np

__all__ = ['SeqFile',]

class SeqFile(object):
    """Reader for Norpix .seq movie files.

    Index by frame number (starting from 0), or iterate over 
    (image array, float timestamp) tuples.

    The 'imfloat' attribute provides the same image data, but rescaled to the
    range [0, 1].

    Other attributes provide metadata, including 'height', 'width', and 'imageCount';
    for more information, see code for the __init__() method.

    The 'header' attribute provides a dictionary-like interface to all included
    metadata.
    """
    def __init__(self, filename):
        self.filename = filename
        self._file = open(filename, 'rb')
        self.header = SeqHeader(self._file)
        h = self.header
        # Useful metadata
        self.height = h['Height']
        self.width = h['Width']
        self.realbpp = h['BitDepthReal']
        self.fullscale = 2**self.realbpp - 1
        # imageCount is computed from the file size, below.
        # Alternate image formats
        self.imfloat = SeqImageFloat(self)
        # Format parameters
        self.bpp = h['BitDepth']
        if h['Version'] == 5: # if StreamPix version 6
            self._imageOffset = 8192
        else: # previous versions
            self._imageOffset = 1024
        self._imageBlockSize = h['TrueImageSize']
        self.filesize = os.stat(filename).st_size
        self.imageCount = (self.filesize - h['HeaderSize']) / h['TrueImageSize']
        # (Note that we do not verify that this platform is little-endian)
        self._dtype = np.dtype('uint%i' % self.bpp) # n-bit unsigned integer
        self._pixlen = h['ImageSizeBytes']
        self._timestampStruct = struct.Struct('<LH') # 4-byte unsigned long and 2-byte unsigned short
    def __getitem__(self, i):
        """Returns a tuple of
        (NumPy array of image data, timestamp as floating-point seconds)
        """
        if int(i) != i:
            raise ValueError("Frame numbers can only be integers")
        if i >= self.imageCount:
            raise ValueError("Frame number is out of range: " + str(i))
        self._file.seek(self._imageOffset + self._imageBlockSize * i)
        imdata = np.fromfile(self._file, self._dtype, self._pixlen).reshape((self.height, self.width))
        tsecs, tms = self._timestampStruct.unpack(self._file.read(6))
        return imdata, tsecs + float(tms) / 1000.
    def __len__(self):
        return self.imageCount
    def __iter__(self):
        for i in range(len(self)):
            yield self[i]
class BinParser(UserDict):
    """Base class for extracting many values from a structured binary file."""
    def __init__(self, file):
        self.file = file
        self.format = []
        self.data = {}
        self.marker = 0
        self.offset = 0
    def extendFormat(self, *args):
        self.format.extend(args)
    def readTo(self, place=None, offset=None):
        """Read format up to and including element named 'place'.
        Will stop when it encounters an unmet dependency.
        If 'place' is None, read to end of format spec.
        """
        if offset != None:
            self.offset = offset
        remaining = self.format[self.marker:]
        segment = []
        for f in remaining:
            # The format objects might need to know things in this dict
            # before they can provide their strings.
            f.attach(self.data)
            for d in f.depends:
                if not self.data.has_key(d): break
            segment.append(f)
            if f.name == place: break
        if not segment:
            raise UserWarning, 'Unable to proceed in parsing.'
        self.marker += len(segment)
        fstr = '<' + reduce(str.__add__, [f.fstr() for f in segment])
        segsize = struct.calcsize(fstr)
        self.file.seek(self.offset)
        segstr = self.file.read(segsize)
        result = struct.unpack(fstr, segstr)
        self.offset += segsize
        for f in segment:
            count = f.count()
            if len(result) < count:
                raise IndexError, 'Not enough structure data to fill format callbacks.'
            f.fcb(*result[0:count])
            result = result[count:]
        if result:
            raise IndexError, 'Unclaimed structure data.'
    def alphaitems(self):
        """Alphabetized list of key, value tuples"""
        r = self.data.items()
        r.sort()
        return r
    def checkoffset(self, target, desc=None, ignore=[]):
        """Compare where we should be with where we are."""
        if desc == None:
            desc = 'target position'
        if self.offset - target:
            if self.offset - target not in ignore:
                print 'Warning: distance to nominal %s is %i bytes' % (desc, self.offset - target)
class SeqHeader(BinParser):
    """Header format for NorPix .seq file"""
    def __init__(self, file):
        BinParser.__init__(self, file)
        d = self.data
        self.extendFormat(
                BinDWord('Magic'),
                BinString('Name', 24),
                BinLong('Version'),
                BinLong('HeaderSize'),
                BinString('Description', 512),
                BinDWord('Width'),
                BinDWord('Height'),
                BinDWord('BitDepth'),
                BinDWord('BitDepthReal'),
                BinDWord('ImageSizeBytes'),
                BinDWord('ImageFormat'),
                BinDWord('AllocatedFrames'),
                BinDWord('Origin'),
                BinDWord('TrueImageSize'),
                BinDouble('SuggestedFrameRate'),
                BinLong('DescriptionFormat'),
                )
        self.readTo()
        self.checkoffset(596)
        assert d['HeaderSize'] == 1024
        if d['ImageFormat'] != 100:
            raise IOError('Only uncompressed mono images are supported')
class FilterILI(object):
    """Filter an object that already implements __getitem__, __len__,
    and __iter__.
    """
    def __init__(self, source):
        self.source = source
    def filter(self, i):
        return i
    def __getitem__(self, i):
        return self.filter(self.source[i])
    def __len__(self):
        return len(self.source)
    def __iter__(self):
        return itertools.imap(self.filter, iter(self.source))
class SeqImageFloat(FilterILI):
    """(image, timestamp) tuples with image data normalized to 1.
    """
    def __init__(self, source, fullscale=255):
        FilterILI.__init__(self, source)
        self.fullscale = fullscale
    def filter(self, i):
        return i[0] / float(self.fullscale), i[1]
def ts2dt(ts):
    """Convert a floating-point timestamp to a DateTime instance."""
    return datetime.datetime.fromtimestamp(ts)

# Data types for BinParser
class BinDatum(object):
    def __init__(self, name, depends=[]):
        self.name = name
        self.depends = depends
    def attach(self, file):
        self.fd = file
    def count(self):
        return 0
    def length(self):
        return struct.calcsize(self.fstr())
    def fstr(self):
        return ''
    def fcb(self):
        # Here set entries in self.fd according to the args,
        # which correspond to the format string
        pass
class BinSimple(BinDatum):
    def count(self):
        return 1
    def fcb(self, val):
        self.fd[self.name] = val
class BinByte(BinSimple):
    def fstr(self):
        return 'B'
class BinChar(BinByte):
    def fstr(self):
        return 'b'
class BinWord(BinSimple):
    def fstr(self):
        return 'H'
class BinShort(BinWord):
    def fstr(self):
        return 'h'
BinInt16 = BinShort

class BinDWord(BinSimple):
    def fstr(self):
        return 'L'
BinUInt = BinDWord
class BinBool(BinDWord):
    def fcb(self, val):
        BinSimple.fcb(self, bool(val))
class BinLong(BinDWord):
    def fstr(self):
        return 'l'
BinInt = BinLong
class BinFloat(BinSimple):
    def fstr(self):
        return 'f'
class BinDouble(BinSimple):
    def fstr(self):
        return 'd'
class BinUInt64(BinSimple):
    def fstr(self):
        return 'Q'
class BinPad(BinDatum):
    def __init__(self, bytes=1, depends=[], name='_PAD'):
        BinDatum.__init__(self, name, depends=depends)
        self.bytes = bytes
    def count(self):
        return 0
    def fstr(self):
        return '%ix' % self.bytes
    def fcb(self, *args):
        pass
class BinNull(BinPad):
    """Ignore any BinSimple-derived datum,
    or a BinMeta-derived datum without dependencies.."""
    def __init__(self, cls, name='_PAD'):
        dummy = cls(name)
        dummy.attach({})
        BinPad.__init__(self, bytes=dummy.length(), name=name)
class BinString(BinSimple):
    """Null-terminated."""
    def __init__(self, name, bytes=1, depends=[]):
        BinSimple.__init__(self, name, depends=depends)
        self.bytes = bytes
    def fstr(self):
        return '%is' % self.bytes
    def fcb(self, val):
        i = val.find("\0")
        if i == -1: i = len(val)
        self.fd[self.name] = val[0:i]
class BinIgnore(BinPad):
    """Ignore a datum instance."""
    def __init__(self, datum):
        self.depends = datum.depends
        self.name = '_PAD'
        self.datum = datum
    def attach(self, file):
        self.datum.attach(file)
    def fstr(self):
        return '%ix' % struct.calcsize(self.datum.fstr())
    def fcb(self, *args): pass
class BinMeta(BinDatum):
    """Make a composite datum out of several other data.
    Results are stored in the main dict as "'name'.'subname'"
    """
    def __init__(self, name, format=[], depends=[]):
        BinDatum.__init__(self, name, depends=depends)
        self.format = format
        self.data = {}
    def formatHook(self):
        return
    def attach(self, file):
        self.fd = file
        self.formatHook()
        for f in self.format:
            f.attach(self.data)
    def count(self):
        return reduce(int.__add__, [f.count() for f in self.format])
    def fstr(self):
        return reduce(str.__add__, [f.fstr() for f in self.format])
    def extraValuesHook(self):
        return
    def fcb(self, *args):
        for f in self.format:
            cnt = f.count()
            f.fcb(*args[0:cnt])
            args = args[cnt:]
        self.extraValuesHook()
        for k, v in self.data.items():
            self.fd['%s.%s' % (self.name, k)] = v
class BinArray(BinMeta):
    """Arrays of single-valued data."""
    def __init__(self, name, element, count, args=[], depends=[]):
	BinMeta.__init__(self, name, depends=depends,
		format=[element(*((i,) + tuple(args))) for i in range(count)])
    def fcb(self, *args):
	for f in self.format:
	    cnt = f.count()
	    f.fcb(*args[0:cnt])
	    args = args[cnt:]
	r = []
	for i in range(len(self.format)):
	    r.append(self.data[i])
	self.fd[self.name] = r
