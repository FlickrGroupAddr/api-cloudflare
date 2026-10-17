-- Original synthetic pixels and bounded header observations only; no SDK or IO.
local M = {}
local MAX_BYTES, MAX_PARTS = 1024 * 1024, 4096
local function le16(n) return string.char(n % 256, math.floor(n / 256) % 256) end
local function le32(n) return le16(n % 65536) .. le16(math.floor(n / 65536)) end

function M.tiff()
    local entries, count = {}, 10
    local bitsOffset = 8 + 2 + count * 12 + 4
    local pixelsOffset = bitsOffset + 6
    local function entry(tag, kind, size, value)
        entries[#entries + 1] = le16(tag) .. le16(kind) .. le32(size) .. le32(value)
    end
    entry(256, 4, 1, 8); entry(257, 4, 1, 8)
    entry(258, 3, 3, bitsOffset); entry(259, 3, 1, 1)
    entry(262, 3, 1, 2); entry(273, 4, 1, pixelsOffset)
    entry(277, 3, 1, 3); entry(278, 4, 1, 8)
    entry(279, 4, 1, 192); entry(284, 3, 1, 1)
    local pixels = {}
    for y = 0, 7 do
        for x = 0, 7 do pixels[#pixels + 1] = string.char(x * 32, y * 32, (x + y) * 16) end
    end
    return 'II' .. le16(42) .. le32(8) .. le16(count) .. table.concat(entries)
        .. le32(0) .. le16(8) .. le16(8) .. le16(8) .. table.concat(pixels)
end

local function be(bytes, start, size)
    local value = 0
    for i = start, start + size - 1 do value = value * 256 + string.byte(bytes, i) end
    return value
end
local function observation(format, depth, width, height, srgb, icc)
    return { format = format, bitDepth = depth, width = width, height = height,
        srgbMarker = srgb, iccMarker = icc, profileVerified = false }
end
local function xor(a, b)
    local result, place = 0, 1
    for _ = 1, 32 do
        if a % 2 ~= b % 2 then result = result + place end
        a, b, place = math.floor(a / 2), math.floor(b / 2), place * 2
    end
    return result
end
local crcTable = {}
for i = 0, 255 do
    local value = i
    for _ = 1, 8 do
        if value % 2 == 1 then value = xor(math.floor(value / 2), 3988292384)
        else value = math.floor(value / 2) end
    end
    crcTable[i] = value
end
local function crc(bytes, first, last)
    local value = 4294967295
    for i = first, last do
        value = xor(math.floor(value / 256), crcTable[xor(value % 256, bytes:byte(i))])
    end
    return 4294967295 - value
end
local function png(bytes)
    local pos, parts, header, data, endedData, palette = 9, 0, false, false, false, false
    local width, height, depth, color, srgb, icc = nil, nil, nil, nil, false, false
    local dataBytes = 0
    while pos <= #bytes do
        parts = parts + 1
        if parts > MAX_PARTS or pos + 11 > #bytes then return nil end
        local length, kind = be(bytes, pos, 4), bytes:sub(pos + 4, pos + 7)
        local first, last = pos + 8, pos + 7 + length
        if last + 4 > #bytes or not kind:match('^[A-Za-z][A-Za-z][A-Z][A-Za-z]$')
            or crc(bytes, pos + 4, last) ~= be(bytes, last + 1, 4) then return nil end
        if not header and kind ~= 'IHDR' then return nil end
        if kind == 'IHDR' then
            if header or length ~= 13 then return nil end
            width, height, depth, color = be(bytes, first, 4), be(bytes, first + 4, 4),
                bytes:byte(first + 8), bytes:byte(first + 9)
            local allowed = { [0] = {1,2,4,8,16}, [2] = {8,16}, [3] = {1,2,4,8},
                [4] = {8,16}, [6] = {8,16} }
            local valid = false
            for _, value in ipairs(allowed[color] or {}) do if depth == value then valid = true end end
            if not valid or width == 0 or height == 0 or width > 2147483647
                or height > 2147483647 or bytes:byte(first + 10) ~= 0
                or bytes:byte(first + 11) ~= 0 or bytes:byte(first + 12) > 1 then return nil end
            header = true
        elseif kind == 'PLTE' then
            if palette or data or color == 0 or color == 4 or length == 0 or length > 768
                or length % 3 ~= 0 or (color == 3 and length / 3 > 2 ^ depth) then return nil end
            palette = true
        elseif kind == 'sRGB' then
            if srgb or icc or data or palette or length ~= 1 or bytes:byte(first) > 3 then return nil end
            srgb = true
        elseif kind == 'iCCP' then
            local zero = bytes:find('\0', first, true)
            if icc or srgb or data or palette or not zero or zero < first + 1
                or zero > first + 79 or zero + 2 > last or bytes:byte(zero + 1) ~= 0 then return nil end
            icc = true -- compressed profile presence only; no profile validation
        elseif kind == 'IDAT' then
            if endedData or (color == 3 and not palette) then return nil end
            data = true
            dataBytes = dataBytes + length
        elseif kind == 'IEND' then
            if length ~= 0 or not data or dataBytes == 0 or last + 4 ~= #bytes then return nil end
            return observation('PNG', depth, width, height, srgb, icc)
        elseif kind:byte(1) < 97 then return nil end
        if data and kind ~= 'IDAT' then endedData = true end
        pos = last + 5
    end
    return nil
end

local function jpeg(bytes)
    local pos, parts, frame, scan, icc = 3, 0, false, false, false
    local width, height, depth, components
    local iccCount, iccParts = nil, {}
    while pos <= #bytes do
        parts = parts + 1
        if parts > MAX_PARTS or bytes:byte(pos) ~= 255 then return nil end
        while bytes:byte(pos) == 255 do pos = pos + 1 end
        local marker = bytes:byte(pos)
        if not marker then return nil end
        pos = pos + 1
        if marker == 217 then
            if not frame or not scan or pos ~= #bytes + 1 then return nil end
            if iccCount then for i = 1, iccCount do if not iccParts[i] then return nil end end end
            return observation('JPEG', depth, width, height, false, icc)
        end
        if marker == 0 or marker == 216 or marker == 1 or (marker >= 208 and marker <= 215)
            or pos + 1 > #bytes then return nil end
        local length = be(bytes, pos, 2)
        local first, last = pos + 2, pos + length - 1
        if length < 2 or last > #bytes then return nil end
        if not ((marker >= 192 and marker <= 207) or marker == 218 or marker == 219
            or marker == 221 or (marker >= 224 and marker <= 239) or marker == 254) then return nil end
        if marker >= 192 and marker <= 207 and marker ~= 196 and marker ~= 200 and marker ~= 204 then
            if frame or (marker ~= 192 and marker ~= 193 and marker ~= 194) or length < 11 then return nil end
            depth, height, width, components = bytes:byte(first), be(bytes, first + 1, 2),
                be(bytes, first + 3, 2), bytes:byte(first + 5)
            if width == 0 or height == 0 or (depth ~= 8 and depth ~= 12)
                or (marker == 192 and depth ~= 8) or components < 1 or components > 4
                or length ~= 8 + 3 * components then return nil end
            local ids = {}
            for i = 0, components - 1 do
                local at = first + 6 + i * 3
                local id, sampling, tableId = bytes:byte(at, at + 2)
                if ids[id] or sampling % 16 < 1 or sampling % 16 > 4
                    or math.floor(sampling / 16) < 1 or math.floor(sampling / 16) > 4
                    or tableId > 3 then return nil end
                ids[id] = true
            end
            frame = ids
        elseif marker == 226 and bytes:sub(first, first + 11) == 'ICC_PROFILE\0' then
            if length < 17 then return nil end
            local sequence, count = bytes:byte(first + 12, first + 13)
            if sequence == 0 or count == 0 or sequence > count or iccParts[sequence]
                or (iccCount and count ~= iccCount) then return nil end
            icc, iccCount, iccParts[sequence] = true, count, true
        elseif marker == 218 then
            if not frame or length < 8 then return nil end
            local selected = bytes:byte(first)
            if selected < 1 or selected > components or length ~= 6 + 2 * selected then return nil end
            local seen = {}
            for i = 0, selected - 1 do
                local id, tables = bytes:byte(first + 1 + i * 2, first + 2 + i * 2)
                if not frame[id] or seen[id] or tables % 16 > 3 or math.floor(tables / 16) > 3 then return nil end
                seen[id] = true
            end
            scan = true
            pos = last + 1
            while pos <= #bytes do
                if bytes:byte(pos) == 255 then
                    local nextByte = bytes:byte(pos + 1)
                    if nextByte == 0 or (nextByte and nextByte >= 208 and nextByte <= 215) then pos = pos + 2
                    else break end
                else pos = pos + 1 end
            end
        end
        if marker ~= 218 then pos = last + 1 end
    end
    return nil
end

function M.inspect(bytes)
    if type(bytes) ~= 'string' or #bytes < 4 or #bytes > MAX_BYTES then return nil end
    if bytes:sub(1, 8) == '\137PNG\13\10\26\10' then return png(bytes) end
    if bytes:sub(1, 2) == '\255\216' then return jpeg(bytes) end
    return nil
end
return M
