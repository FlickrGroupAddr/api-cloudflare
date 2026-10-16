-- Copyright 2026 Terry Ott. MIT License.
-- Unregistered candidate. show runs only inside the composition's owned SDK task.
local View={PRODUCTION_QUALIFIED=false}
local messages={unavailable='Submission status is unavailable.',
    response_invalid='Submission status is unavailable.',
    status_changed='Submission status changed during refresh.',
    authentication_unconfirmed='The connection could not be confirmed.',
    invalid_request='Submission status is unavailable.',cancelled='Submission status closed.'}
function View.model(controller)
    local m=controller.model
    local rows={}
    if m.data then
        for _,v in ipairs(m.data.intents) do
            local presentation=controller.d.client.presentation(v,m.data.observedAt,controller.d.jsonNull)
            if not presentation then return {notice=messages.response_invalid,rows={},readOnly=true} end
            -- Names are historical observations; exact retained identity is always visible.
            rows[#rows+1]={id=v.fgaSubmissionIntentId,groupId=v.flickrGroupId,
                title=v.flickrGroupId..' — '..presentation.text,readOnly=true}
        end
    end
    return {notice=m.stale and 'Stale — showing the last complete status.'
        or m.data and 'Retained group submission status.' or messages[m.reason] or messages.unavailable,
        rows=rows,readOnly=true}
end
function View.show(controller, context, task)
    -- task supplies start(function) and sliced/cancellable sleep from the owned context.
    if type(task)~='table' or type(task.start)~='function' or type(task.sleep)~='function'
        or type(context)~='table' or type(context.addCleanupHandler)~='function' then return nil,'invalid_request' end
    local LrBinding,LrDialogs,LrView=import 'LrBinding',import 'LrDialogs',import 'LrView'
    local f,bind=LrView.osFactory(),LrView.bind
    local p=LrBinding.makePropertyTable(context)
    local function sync()
        local model=View.model(controller)
        local lines={}
        for _,row in ipairs(model.rows) do lines[#lines+1]=row.id..' | '..row.title end
        p.notice,p.details=model.notice,table.concat(lines,'\n\n')
    end
    context:addCleanupHandler(function() controller:close() end)
    controller:open(); sync()
    task.start(function()
        while controller.visible do
            controller:tick()
            sync()
            if not controller:valid() then controller:close(); break end
            task.sleep(1)
        end
    end)
    local answer=LrDialogs.presentModalDialog {title='FlickrGroupAddr — Submission status',
        actionVerb='Close',cancelVerb='Close',contents=f:column {bind_to_object=p,
            f:static_text {title=bind 'notice',width_in_chars=96},
            f:edit_field {value=bind 'details',enabled=false,width_in_chars=96,height_in_lines=18},
            f:push_button {title='Refresh status',action=function() controller:refresh() end},
        }}
    controller:close()
    return answer
end
return View
