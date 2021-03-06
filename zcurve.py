from direction import D
from geohash import Geohash

class ZCurve(object):
    '''
    Represents a position on a Z-Order Curve in 2D                    0 - 1
    https://en.wikipedia.org/wiki/Z-order_curve                         /
    https://en.wikipedia.org/wiki/Moser%E2%80%93de_Bruijn_sequence    2 - 3
    '''

    EVENBITS = 0xaaaaaaaa # 0b10101010101010101010101010101010 (32 bit)
    ODDBITS  = 0x55555555 # 0b01010101010101010101010101010101 (32 bit)

    z = 0
    depth = 0
    halfsplit = False

    def __init__(self, z=0, depth=1, halfsplit=False):
        '''
        `z`      is the position on the z-order curve.

        `depth`  is the recursion depth of the curve.
            A ZCurve can have `4**depth` elements

        `halfsplit` indicates that this instance covers double the area on the X
            axis (itself + neighbouring cell), due to an uneven number of splits

        TODO: should we implement the halfsplit like this? we might run into uglyness
            when calculating neighbours, children...
            It's basically an depth offset for the X axis, so treat it numerically?

        TODO: implement halfsplit for all the operators:
            - [x] __str__
            - [x] __eq__
            - [ ] __gt__, lt, ge, le
            - [ ] __add__
            - [ ] __contains__
            - [ ] parent
            - [ ] children
            - [ ] neighbours
            - [ ] region
        '''

        # shorthand to construct from bitstring
        if type(z) == str:
            _ = ZCurve.fromBitstring(z)
            self.z = _.z
            self.depth = _.depth
            self.halfsplit = _.halfsplit
            return

        if z > 4 ** depth - 1:
            raise ValueError('z-value %i does not exist on depth level %i' % (z, depth))

        self.z = z
        self.depth = depth
        self.halfsplit = halfsplit

    def fromXY(xy, depth):
        '''
        Constructs a ZCurve instance from a x,y pair, where x,y are indices to
        the moser-debruijn sequence, so z = debruijn[x] + 2*debruijn[y]
        '''
        x, y = xy
        if x >= 2 ** depth or y >= 2 ** depth:
            raise ValueError('coordinate %s does not exist on depth level %i' % (xy, depth))

        # interleave bits https://graphics.stanford.edu/~seander/bithacks.html#InterleaveTableObvious
        z = 0
        for i in range(32):
            z |= (x & 1 << i) << i | (y & 1 << i) << (i + 1)

        return ZCurve(z, depth)

    def fromBitstring(bitstring):
        # uneven number of bits means we have a halfsplit:
        # set last split on X to 0, but we treat it as covering both 0 and 1
        halfsplit = len(bitstring) % 2 != 0
        if halfsplit:
            bitstring += '0'

        depth = int(len(bitstring) / 2)
        z = int(bitstring, base=2)
        return ZCurve(z, depth, halfsplit)

    def fromLatLon(lat, lon, depth, halfsplit=False):
        z = Geohash.encodePoint(lat, lon, depth * 2, Geohash.NUMERIC_MSB)
        return ZCurve(z, depth, halfsplit)

    def xy(self):
        ''' returns indices to the debruijn sequence
        '''
        x = 0
        y = 0
        # de-interleave bits
        for i in range(32):
            if i % 2 == 0:
                x |= (self.z & 1 << i) >> int(i / 2)
            else:
                y |= (self.z & 1 << i) >> int(i / 2 + 1)
        return x, y

    def debruijn(self):
        ''' given indices to the moser-debuijn sequence, returns debruijn values
        '''
        xDebruijn = self.z & self.ODDBITS
        yDebruijn = self.z & self.EVENBITS
        return xDebruijn, yDebruijn

    def region(self, minXy=None, maxXy=None):
        '''
        returns the covered region as `((minX, minY), (maxX, maxY))` tuple
        scaled to the `minXy` and `maxXy` range
        '''
        minXy = minXy or (-180, -90)
        maxXy = maxXy or (180, 90)

        if self.depth == 0:
            return minXy, maxXy

        x, y = self.xy()
        numY = 2 ** self.depth
        numX = numY / 2 if self.halfsplit else numY

        rangeX = maxXy[0] - minXy[0]
        rangeY = maxXy[1] - minXy[1]
        minX = minXy[0] + x * rangeX / numX
        minY = minXy[1] + y * rangeY / numY
        maxX = minX + rangeX / numX
        maxY = minY + rangeY / numY

        return (minX, minY), (maxX, maxY)

    def neighbours(self):
        # https://en.wikipedia.org/wiki/Z-order_curve#Coordinate_values adapted to 32bit
        return {
            D.NORTH: ZCurve((((self.z & self.EVENBITS) - 1 & self.EVENBITS) | (self.z & self.ODDBITS)) % 4 ** self.depth, self.depth),
            D.SOUTH: ZCurve((((self.z | self.ODDBITS)  + 1 & self.EVENBITS) | (self.z & self.ODDBITS)) % 4 ** self.depth, self.depth),
            D.WEST:  ZCurve((((self.z & self.ODDBITS)  - 1 & self.ODDBITS) | (self.z & self.EVENBITS)) % 4 ** self.depth, self.depth),
            D.EAST:  ZCurve((((self.z | self.EVENBITS) + 1 & self.ODDBITS) | (self.z & self.EVENBITS)) % 4 ** self.depth, self.depth),
        }

    def parent(self, depthOffset=1):
        ''' returns the corresponding cell in the z-order curve of one less recursion
        '''
        z = self.z >> (2 * depthOffset)
        depth = max(0, self.depth - depthOffset)
        return ZCurve(z, depth)

    def children(self, depthOffset=1):
        ''' returns the corresponding cells in the z-order curve of deeper recurson
        '''
        zBase = self.z << (2 * depthOffset)
        numChildren = 4 ** depthOffset
        return [ZCurve(z, self.depth + depthOffset) for z in range(zBase, zBase + numChildren)]

    def __str__(self):
        # encode as bitstring
        res = ''
        skipLsb = 1 if self.halfsplit else 0 # don't encode the last X-axis split
        for i in range(skipLsb, self.depth * 2):
            bit = (self.z & (1 << i)) >> i
            res += str(bit)
        return res[::-1] # reverse, MSB first

    def __add__(self, other):
        self.ensureSameType(other)

        if other.depth != self.depth:
            deeper = other if self.depth < other.depth else self
            higher = self  if self.depth < other.depth else other
            return deeper + higher.children(deeper.depth - higher.depth)[0]

        # https://en.wikipedia.org/wiki/Z-order_curve#Coordinate_values adapted to 32bit
        z = (
            ((self.z | self.EVENBITS) + (other.z & self.ODDBITS) & self.ODDBITS) |
            ((self.z | self.ODDBITS) + (other.z & self.EVENBITS) & self.EVENBITS)
        ) % 4 ** self.depth
        return ZCurve(z, self.depth)

    def __contains__(self, other):
        self.ensureSameType(other)
        if self.depth > other.depth:
            return False
        elif self.depth < other.depth:
            # we're larger, but we need to check overlap
            # TODO: self.halfsplit
            return self == other.parent(other.depth - self.depth)
        else:
            return self == other

    def __lt__(self, other):
        # compares the "area" that this instance covers
        self.ensureSameType(other)
        return self.depth > other.depth

    def __gt__(self, other):
        self.ensureSameType(other)
        return self.depth < other.depth

    def __le__(self, other):
        self.ensureSameType(other)
        return self.depth <= other.depth

    def __ge__(self, other):
        self.ensureSameType(other)
        return self.depth >= other.depth

    def __eq__(self, other):
        self.ensureSameType(other)
        return (
            self.z == other.z and
            self.depth == other.depth and
            self.halfsplit == other.halfsplit
        )

    def ensureSameType(self, other):
        if type(other) != ZCurve:
            raise TypeError('cant compare ZCurve with %s', type(other))
