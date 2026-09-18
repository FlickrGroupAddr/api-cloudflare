local LrView = import "LrView"

local Controller = require "ConnectionController"
local bind = LrView.bind

local function sectionsForTopOfDialog(factory, properties)
    Controller.initialize(properties)
    properties:addObserver("pluginCodeUrl", function()
        Controller.restoreUrl(properties)
    end)

    return {
        {
            title = "FGA-LrC15 connection",
            synopsis = bind { key = "status", bind_to_object = properties },
            factory:column {
                bind_to_object = properties,
                spacing = factory:control_spacing(),
                fill_horizontal = 1,

                factory:static_text {
                    title = "Open this address yourself in a private browser window:",
                    fill_horizontal = 1,
                },
                factory:edit_field {
                    value = bind "pluginCodeUrl",
                    immediate = true,
                    width_in_chars = 48,
                    fill_horizontal = 1,
                },
                factory:static_text {
                    title = "Paste the one-time Plugin Code below. Compare it with the browser display before storing it.",
                    width_in_chars = 72,
                    height_in_lines = -1,
                    fill_horizontal = 1,
                },
                factory:edit_field {
                    value = bind "pluginCode",
                    immediate = true,
                    enabled = bind "canStore",
                    width_in_chars = 64,
                    fill_horizontal = 1,
                    font = { name = "Consolas", size = 18 },
                },
                factory:row {
                    spacing = factory:control_spacing(),
                    factory:push_button {
                        title = "Store and verify",
                        enabled = bind "canStore",
                        action = function() Controller.storeAndVerify(properties) end,
                    },
                    factory:push_button {
                        title = "Verify stored credential",
                        enabled = bind "hasStoredCode",
                        action = function() Controller.verifyStored(properties) end,
                    },
                },
                factory:static_text {
                    title = bind "status",
                    width_in_chars = 72,
                    height_in_lines = -1,
                    fill_horizontal = 1,
                },
                factory:row {
                    factory:static_text { title = "Installation:" },
                    factory:static_text {
                        title = bind "installation",
                        fill_horizontal = 1,
                    },
                },
                factory:static_text {
                    title = "This release performs only the read-only connection check. It cannot publish or add a photo to a Flickr group.",
                    width_in_chars = 72,
                    height_in_lines = -1,
                    fill_horizontal = 1,
                },
            },
        },
    }
end

return {
    sectionsForTopOfDialog = sectionsForTopOfDialog,
}
