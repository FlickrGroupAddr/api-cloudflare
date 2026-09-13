// Closed schemas mirror the accepted Plugin Code HTTP projection.
const schemas:Record<string,unknown> = {
  "PluginCodeCredential": {
    "type": "string",
    "minLength": 64,
    "maxLength": 64,
    "pattern": "^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){11}-[0-9A-HJKMNP-TV-Z]{3}[0G]$",
    "description": "ADR 0044 canonical encoding of exactly 32 random octets: 52 uppercase Crockford Base32 symbols in 13 four-symbol groups separated by ASCII hyphens. The hyphens are part of the credential; parsers perform no normalization or repair."
  },
  "PluginCodeCreation": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "pluginCodeId",
      "pluginCode"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "pluginCodeId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "pluginCode": {
        "$ref": "#/components/schemas/PluginCodeCredential"
      }
    }
  },
  "PluginCodeStatePatch": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "state"
    ],
    "properties": {
      "state": {
        "type": "string",
        "const": "revoked"
      }
    }
  },
  "PluginCodeTransferConfirmations": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "ownerControlledWorkstation",
      "privateBrowser",
      "clipboardHistoryOff",
      "clipboardSyncOff",
      "noObserversOrRecording",
      "pluginReady"
    ],
    "properties": {
      "ownerControlledWorkstation": {
        "const": true
      },
      "privateBrowser": {
        "const": true
      },
      "clipboardHistoryOff": {
        "const": true
      },
      "clipboardSyncOff": {
        "const": true
      },
      "noObserversOrRecording": {
        "const": true
      },
      "pluginReady": {
        "const": true
      }
    }
  },
  "PluginCodeCreateRequest": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "installationLabel",
      "transferConfirmations"
    ],
    "properties": {
      "schemaVersion": {
        "const": 1
      },
      "installationLabel": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120
      },
      "transferConfirmations": {
        "$ref": "#/components/schemas/PluginCodeTransferConfirmations"
      }
    }
  },
  "PluginCodeCandidateRequest": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "transferConfirmations"
    ],
    "properties": {
      "schemaVersion": {
        "const": 1
      },
      "transferConfirmations": {
        "$ref": "#/components/schemas/PluginCodeTransferConfirmations"
      }
    }
  },
  "PluginCodeCandidatePatch": {
    "oneOf": [
      {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "schemaVersion",
          "state",
          "pluginValidationConfirmed"
        ],
        "properties": {
          "schemaVersion": {
            "const": 1
          },
          "state": {
            "const": "current"
          },
          "pluginValidationConfirmed": {
            "const": true
          }
        }
      },
      {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "schemaVersion",
          "state"
        ],
        "properties": {
          "schemaVersion": {
            "const": 1
          },
          "state": {
            "const": "revoked"
          }
        }
      }
    ]
  },
  "PluginCodeCandidateCreation": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "pluginCodeId",
      "rotationCandidateId",
      "pluginCode",
      "expiresAt"
    ],
    "properties": {
      "schemaVersion": {
        "const": 1
      },
      "pluginCodeId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "rotationCandidateId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "pluginCode": {
        "$ref": "#/components/schemas/PluginCodeCredential"
      },
      "expiresAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      }
    }
  },
  "PluginCodeVersion": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "versionId",
      "state",
      "createdAt",
      "expiresAt"
    ],
    "properties": {
      "versionId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "state": {
        "enum": [
          "current",
          "pending_rotation",
          "replaced",
          "revoked",
          "expired_unactivated"
        ]
      },
      "createdAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "expiresAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      }
    }
  },
  "PluginCodeLifecycleOutcome": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "kind",
      "versionId",
      "occurredAt"
    ],
    "properties": {
      "kind": {
        "enum": [
          "created",
          "rotation_created",
          "rotation_completed",
          "rotation_cancelled",
          "rotation_expired",
          "revoked"
        ]
      },
      "versionId": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/OpaqueId"
          },
          {
            "type": "null"
          }
        ]
      },
      "occurredAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      }
    }
  },
  "PluginCodeDetail": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "pluginCodeId",
      "installationLabel",
      "state",
      "revision",
      "createdAt",
      "revokedAt",
      "lastAuthenticatedAt",
      "rotationDueAt",
      "currentVersion",
      "pendingCandidate",
      "lastLifecycleOutcome"
    ],
    "properties": {
      "schemaVersion": {
        "const": 1
      },
      "pluginCodeId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "installationLabel": {
        "type": "string",
        "maxLength": 120
      },
      "state": {
        "enum": [
          "active",
          "revoked"
        ]
      },
      "revision": {
        "$ref": "#/components/schemas/Revision"
      },
      "createdAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "revokedAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "lastAuthenticatedAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "rotationDueAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "currentVersion": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PluginCodeVersion"
          },
          {
            "type": "null"
          }
        ]
      },
      "pendingCandidate": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PluginCodeVersion"
          },
          {
            "type": "null"
          }
        ]
      },
      "lastLifecycleOutcome": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PluginCodeLifecycleOutcome"
          },
          {
            "type": "null"
          }
        ]
      }
    }
  },
  "PluginCodePage": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "pluginCodes"
    ],
    "properties": {
      "schemaVersion": {
        "const": 1
      },
      "pluginCodes": {
        "type": "array",
        "maxItems": 100,
        "items": {
          "$ref": "#/components/schemas/PluginCodeDetail"
        }
      },
      "nextPageToken": {
        "type": "string",
        "maxLength": 2048
      }
    }
  },
  "OpaqueId": {
    "type": "string",
    "minLength": 1,
    "description": "Opaque identifier; clients do not parse, increment, or derive authority from its spelling."
  },
  "Revision": {
    "type": "integer",
    "minimum": 1
  },
  "PreciseTimestamp": {
    "type": "string",
    "format": "date-time",
    "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$"
  }
};
export function pluginCodeSchema(name:string):unknown {
 const expand=(value:unknown):unknown=>{
  if(Array.isArray(value))return value.map(expand);
  if(value&&typeof value==="object"){
   const record=value as Record<string,unknown>;
   if(typeof record.$ref==="string")return expand(schemas[record.$ref.split("/").at(-1)!]);
   return Object.fromEntries(Object.entries(record).map(([key,entry])=>[key,expand(entry)]));
  }return value;
 };return expand(schemas[name]);
}
const common={owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,expectedChallenge:null,handler:"plugin_code",auth:"browser_session",allowPending:false} as const;
export const PLUGIN_CODE_ROUTES = [
 {...common,id:"listPluginCodes",method:"GET",pathPattern:"/api/v001/plugin-codes",successStatuses:[200],request:null,response:pluginCodeSchema("PluginCodePage")},
 {...common,id:"createPluginCode",method:"POST",pathPattern:"/api/v001/plugin-codes",successStatuses:[201],request:pluginCodeSchema("PluginCodeCreateRequest"),response:pluginCodeSchema("PluginCodeCreation")},
 {...common,id:"getPluginCode",method:"GET",pathPattern:"/api/v001/plugin-codes/{pluginCodeId}",successStatuses:[200],request:null,response:pluginCodeSchema("PluginCodeDetail")},
 {...common,id:"revokePluginCode",method:"PATCH",pathPattern:"/api/v001/plugin-codes/{pluginCodeId}",successStatuses:[200],request:pluginCodeSchema("PluginCodeStatePatch"),requestMediaType:"application/merge-patch+json",response:pluginCodeSchema("PluginCodeDetail")},
 {...common,id:"createPluginCodeRotationCandidate",method:"POST",pathPattern:"/api/v001/plugin-codes/{pluginCodeId}/rotation-candidates",successStatuses:[201],request:pluginCodeSchema("PluginCodeCandidateRequest"),response:pluginCodeSchema("PluginCodeCandidateCreation")},
 {...common,id:"changePluginCodeRotationCandidate",method:"PATCH",pathPattern:"/api/v001/plugin-codes/{pluginCodeId}/rotation-candidates/{rotationCandidateId}",successStatuses:[200],request:pluginCodeSchema("PluginCodeCandidatePatch"),response:pluginCodeSchema("PluginCodeDetail")},
] as const;
