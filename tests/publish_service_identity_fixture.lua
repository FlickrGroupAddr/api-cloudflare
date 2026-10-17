Client=require 'PublishServiceIdentityClient'
function identity(id)
 return {schemaVersion=1,fgaPublishServiceId=id or '11111111-1111-4111-8111-111111111111',
  issuingInstallationId='install',linkedFlickrRevision=1,serviceRevision=1}
end
function clone(v)
 if type(v)~='table' then return v end local out={} for k,x in pairs(v) do out[k]=clone(x) end return out
end
function fixture()
 local f={posts=0,gets=0,saves=0,locked=false,settings={}}
 f.deps={
  withServiceLock=function(settings,fn) assert(settings==f.settings and not f.locked);f.locked=true
   local ok,result=pcall(fn);f.locked=false;if not ok then error('sanitized') end return result end,
  read=function(settings) assert(settings==f.settings and f.locked);return clone(f.saved) end,
  save=function(settings,value) assert(settings==f.settings and f.locked);f.saves=f.saves+1;f.saved=clone(value);return true end,
  hasRetainedRecords=function() return f.retained or false end,
  request=function(method,path,body)
   assert(f.locked)
   local v=identity()
   if method=='POST' then f.posts=f.posts+1;assert(body.schemaVersion==1 and path=='/api/v001/publish-services')
   else f.gets=f.gets+1;v=clone(f.remote or f.saved);assert(path=='/api/v001/publish-services/'..f.saved.fgaPublishServiceId) end
   v.linkStatus=f.linkStatus or 'ready'
   return {status=method=='POST' and 201 or 200,body=v,headers={['Cache-Control']='no-store',
    ['X-Content-Type-Options']='nosniff',['Referrer-Policy']='no-referrer',Location='/api/v001/publish-services/'..v.fgaPublishServiceId}}
  end
 }
 function f:client() return Client.new(self.deps) end
 return f
end
