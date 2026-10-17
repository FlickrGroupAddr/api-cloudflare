-- Original FGA SDK-boundary fixture. Never imports network/catalog/native APIs.
local files, calls = {}, {}
function import(name)
    if name == 'LrTasks' then return { pcall = pcall } end
    assert(name == 'LrFileUtils', 'unexpected SDK capability: ' .. tostring(name))
    return {
        exists = function(path)
            calls.inspect = calls.inspect + 1
            local file = files[path]
            if file and file.inspectError then error('private file detail') end
            return file and file.kind or nil
        end,
        fileAttributes = function(path)
            local file = files[path]
            return file and {fileSize=file.size, fileModificationDate=file.modified or 1}
        end,
        readFile = function(path)
            calls.read = calls.read + 1
            local file = files[path]
            if not file or file.unreadable then error('private read detail') end
            return file.contents
        end,
    }
end

local Fixture = {}
function Fixture.new()
    files, calls = {}, {wait=0, inspect=0, read=0, consume=0}
    local f = {files=files, calls=calls, cancelled=false, current=true}
    f.context = {photoUuid='synthetic-photo', selectionRevision=1, groups={}}
    f.deps = {
        cancelled = function() return f.cancelled end,
        current = function(context)
            assert(context == f.context)
            return f.current
        end,
    }
    f.events={}
    function f:rendition(path, success)
        return {photo={uuid='synthetic-photo'}, waitForRender=function()
            calls.wait=calls.wait+1
            self.events[#self.events+1]='wait'
            if self.onWait then self.onWait() end
            if self.waitThrows then error('private wait detail') end
            return success ~= false, path
        end}
    end
    function f:file(path, contents)
        files[path]={kind='file', size=#contents, contents=contents}
    end
    function f:consume(lease, context, config)
        calls.consume=calls.consume+1
        assert(context==self.context)
        self.lease, self.config=lease, config
        local bytes, reason=lease:read()
        self.bytes, self.reason=bytes, reason
        return bytes ~= nil
    end
    return f
end
return Fixture
