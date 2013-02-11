# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

import norpix

# <codecell>

ls

# <markdowncell>

# Files are read with instances of the `SeqFile` class.

# <codecell>

norpix.SeqFile?
# Or, the non-interactive version:
print norpix.SeqFile.__doc__

# <codecell>

# Open the file
seqfile = norpix.SeqFile('sample.seq')

# <markdowncell>

# Retrieving frame data
# ====
# 
# `seqfile` now acts much like a regular Python list. Each frame is retrieved as an (`image data`, `timestamp`) tuple. `timestamp` is the number of seconds elapsed since a fixed reference date.

# <codecell>

print len(seqfile), 'frames total'

# <codecell>

image_data, timestamp = seqfile[0]
print type(image_data)
print type(timestamp)

# <codecell>

imshow(image_data)
gray()
axis('equal')

# <markdowncell>

# `ts2dt()` is provided as a convenience to convert timestamps from a `.seq` file to ordinary Python `datetime` instances.

# <markdowncell>

# It's easy to calculate things like the total elapsed time of the movie. For more advanced manipulations, use `norpix.ts2dt()` to get Python `datetime` instances.

# <codecell>

first_ts = seqfile[0][1]
last_ts = seqfile[len(seqfile) - 1][1]
last_ts - first_ts

# <codecell>

timestamp_dt = norpix.ts2dt(first_ts)
print repr(timestamp_dt)
print timestamp_dt
print timestamp_dt.year

# <markdowncell>

# Metadata
# ====
# 
# The attributes of `seqfile` contain a useful subset of the metadata that can be read from each `.seq` file. For a  listing, see `SeqFile.__init__()` in the source code, or just type
# 
# `seqfile.`
# 
# and hit Tab.

# <codecell>

print seqfile.height, seqfile.width

# <markdowncell>

# Converting to another image format
# ====
# 
# The simplest version is very simple:

# <codecell>

import os
import scipy.misc
import norpix
def convert(filename, destdir, ext='PNG'):
    """Convert NorPix .seq file to a series of image files."""
    if not os.path.isdir(destdir):
        os.makedirs(destdir)
    sf = norpix.SeqFile(filename)
    print 'Converting %i frames in %s' % (len(sf), filename)
    for framenum in range(len(sf)):
        imdata, timestamp = sf[framenum]
        destfn = 'frame_%.5i.%s' % (framenum, ext)
        scipy.misc.imsave(os.path.join(destdir, destfn), imdata)

# <codecell>

convert('sample.seq', 'sample_frames')

# <codecell>

ls sample_frames

# <codecell>


