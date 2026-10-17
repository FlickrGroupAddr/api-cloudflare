-- Copyright 2026 Terry Ott. SPDX-License-Identifier: MIT
-- Source/rationale: docs/research/flickr-rendition-policy-2026-10-17.md.
-- 200 MB is provider wording; 200000000 is our conservative decimal ceiling.
local RenditionPolicy = {}

local sourceUrl = "https://www.flickrhelp.com/hc/en-us/articles/4404079649300-Flickr-upload-requirements"
local policyId = "flickr-photo-decimal-200mb-2026-10-17"

function RenditionPolicy.resolve(settings)
    if settings == nil then settings = {} end
    if type(settings) ~= "table" then return nil, "invalid_rendition_settings" end
    local format = settings.LR_format
    if format == nil then format = "PNG" end
    if format ~= "PNG" and format ~= "JPEG" then
        return nil, "unsupported_rendition_format"
    end
    if settings.LR_export_bitDepth ~= nil and settings.LR_export_bitDepth ~= 8 then
        return nil, "unsupported_rendition_depth"
    end
    if settings.LR_export_colorSpace ~= nil and settings.LR_export_colorSpace ~= "sRGB" then
        return nil, "unsupported_rendition_color_space"
    end
    if settings.LR_size_doConstrain ~= nil and settings.LR_size_doConstrain ~= false then
        return nil, "unsupported_rendition_resize"
    end
    if settings.LR_jpeg_useLimitSize ~= nil and settings.LR_jpeg_useLimitSize ~= false then
        return nil, "unsupported_rendition_size_target"
    end
    local quality = settings.LR_jpeg_quality
    if quality == nil then quality = 1 end
    if format == "JPEG" and (type(quality) ~= "number" or quality ~= quality
        or quality < 0 or quality > 1) then
        return nil, "invalid_rendition_jpeg_quality"
    end
    local exportSettings = {
        LR_format = format,
        LR_export_bitDepth = 8,
        LR_export_colorSpace = "sRGB",
        LR_size_doConstrain = false,
        LR_jpeg_useLimitSize = false,
    }
    if format == "JPEG" then exportSettings.LR_jpeg_quality = quality end
    -- Fresh values on every call: mutation cannot change later resolutions.
    return {
        maximumBytes = 200000000,
        format = format,
        exportSettings = exportSettings,
        policyId = policyId,
        sourceUrl = sourceUrl,
        retrievedOn = "2026-10-17",
        byteConvention = "conservative_decimal_engineering_ceiling",
    }
end

return RenditionPolicy
