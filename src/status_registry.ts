// Closed projection from the accepted status contract.
const schemas:Record<string,unknown> = {
  "IntentPage": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "observedAt",
      "view",
      "pageSize",
      "photoBindingId",
      "summary",
      "intents",
      "nextPage",
      "recommendedPollAfterSeconds"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "observedAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "view": {
        "type": "string",
        "enum": [
          "active",
          "attention",
          "history"
        ]
      },
      "pageSize": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100
      },
      "photoBindingId": {
        "type": [
          "string",
          "null"
        ]
      },
      "summary": {
        "$ref": "#/components/schemas/StatusSummary"
      },
      "intents": {
        "type": "array",
        "items": {
          "$ref": "#/components/schemas/SubmissionIntent"
        },
        "maxItems": 100
      },
      "nextPage": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/NextPage"
          },
          {
            "type": "null"
          }
        ]
      },
      "recommendedPollAfterSeconds": {
        "description": "Minimum client read interval only; never worker cadence or an ETA.",
        "type": [
          "integer",
          "null"
        ],
        "enum": [
          15,
          60,
          null
        ]
      }
    }
  },
  "PreciseTimestamp": {
    "type": "string",
    "format": "date-time",
    "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$"
  },
  "StatusSummary": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "activeIntentCount",
      "activePartitionCount",
      "attentionIntentCount",
      "oldestActiveEnqueuedAt",
      "writeGates"
    ],
    "properties": {
      "activeIntentCount": {
        "type": "integer",
        "minimum": 0
      },
      "activePartitionCount": {
        "type": "integer",
        "minimum": 0
      },
      "attentionIntentCount": {
        "type": "integer",
        "minimum": 0
      },
      "oldestActiveEnqueuedAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "writeGates": {
        "type": "array",
        "items": {
          "$ref": "#/components/schemas/GateProjection"
        },
        "maxItems": 2
      }
    }
  },
  "GateProjection": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "scope",
      "state",
      "revision",
      "pausedAt",
      "reasonCode",
      "affectedActiveIntentCount"
    ],
    "properties": {
      "scope": {
        "type": "string",
        "enum": [
          "user",
          "deployment"
        ]
      },
      "state": {
        "type": "string",
        "enum": [
          "enabled",
          "paused"
        ]
      },
      "revision": {
        "$ref": "#/components/schemas/Revision"
      },
      "pausedAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "reasonCode": {
        "type": [
          "string",
          "null"
        ]
      },
      "affectedActiveIntentCount": {
        "type": "integer",
        "minimum": 0
      }
    }
  },
  "Revision": {
    "type": "integer",
    "minimum": 1
  },
  "SubmissionIntent": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "fgaSubmissionIntentId",
      "fgaPhotoBindingId",
      "flickrPhotoId",
      "flickrGroupId",
      "groupDisplayName",
      "groupDisplayNameObservedAt",
      "state",
      "stateRevision",
      "createdAt",
      "stateChangedAt",
      "terminalAt",
      "attemptCount",
      "queue",
      "lastOutcome",
      "permanentSubmissionBlock",
      "attention"
    ],
    "properties": {
      "fgaSubmissionIntentId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "fgaPhotoBindingId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "flickrPhotoId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "flickrGroupId": {
        "$ref": "#/components/schemas/OpaqueId"
      },
      "groupDisplayName": {
        "type": [
          "string",
          "null"
        ]
      },
      "groupDisplayNameObservedAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "state": {
        "$ref": "#/components/schemas/IntentState"
      },
      "stateRevision": {
        "$ref": "#/components/schemas/Revision"
      },
      "createdAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "stateChangedAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "terminalAt": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "attemptCount": {
        "type": "integer",
        "minimum": 0
      },
      "queue": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/IntentQueue"
          },
          {
            "type": "null"
          }
        ]
      },
      "lastOutcome": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/LastOutcome"
          },
          {
            "type": "null"
          }
        ]
      },
      "permanentSubmissionBlock": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/PermanentSubmissionBlock"
          },
          {
            "type": "null"
          }
        ]
      },
      "attention": {
        "oneOf": [
          {
            "$ref": "#/components/schemas/Attention"
          },
          {
            "type": "null"
          }
        ]
      }
    }
  },
  "OpaqueId": {
    "type": "string",
    "minLength": 1,
    "description": "Opaque identifier; clients do not parse, increment, or derive authority from its spelling."
  },
  "IntentState": {
    "type": "string",
    "enum": [
      "queued",
      "attempting",
      "retrying",
      "throttled",
      "added",
      "moderation_submitted",
      "delivery_uncertain",
      "needs_attention",
      "cancelled"
    ]
  },
  "IntentQueue": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "isPartitionHead",
      "activeAheadInPartition",
      "nextWorkNotBefore",
      "holds"
    ],
    "properties": {
      "isPartitionHead": {
        "type": "boolean"
      },
      "activeAheadInPartition": {
        "type": "integer",
        "minimum": 0
      },
      "nextWorkNotBefore": {
        "description": "Advisory database lower bound for head work at observedAt; null for a non-head or an attempt already in progress. This is not an ETA or scheduler-cadence promise.",
        "oneOf": [
          {
            "$ref": "#/components/schemas/PreciseTimestamp"
          },
          {
            "type": "null"
          }
        ]
      },
      "holds": {
        "type": "array",
        "uniqueItems": true,
        "items": {
          "type": "string",
          "enum": [
            "user_flickr_write_gate_paused",
            "deployment_flickr_write_gate_paused"
          ]
        }
      }
    }
  },
  "LastOutcome": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "reasonCode",
      "flickrResultCode",
      "observedAt",
      "correlationId"
    ],
    "properties": {
      "reasonCode": {
        "type": "string",
        "minLength": 1
      },
      "flickrResultCode": {
        "type": [
          "integer",
          "null"
        ]
      },
      "observedAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "correlationId": {
        "$ref": "#/components/schemas/OpaqueId"
      }
    }
  },
  "PermanentSubmissionBlock": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "reasonCode",
      "createdAt"
    ],
    "properties": {
      "reasonCode": {
        "type": "string",
        "minLength": 1
      },
      "createdAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      }
    }
  },
  "Attention": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "kind",
      "reasonCode",
      "occurredAt",
      "operatorAction",
      "fgaResubmissionAllowed"
    ],
    "properties": {
      "kind": {
        "type": "string",
        "enum": [
          "needs_attention",
          "delivery_uncertain"
        ]
      },
      "reasonCode": {
        "type": "string",
        "minLength": 1
      },
      "occurredAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "operatorAction": {
        "type": "string",
        "minLength": 1
      },
      "fgaResubmissionAllowed": {
        "type": "boolean",
        "const": false
      }
    }
  },
  "NextPage": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "beforeCreatedAt",
      "beforeIntentId"
    ],
    "properties": {
      "beforeCreatedAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "beforeIntentId": {
        "$ref": "#/components/schemas/OpaqueId"
      }
    }
  },
  "IntentItem": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "observedAt",
      "intent",
      "writeGates",
      "recommendedPollAfterSeconds"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "observedAt": {
        "$ref": "#/components/schemas/PreciseTimestamp"
      },
      "intent": {
        "$ref": "#/components/schemas/SubmissionIntent"
      },
      "writeGates": {
        "type": "array",
        "items": {
          "$ref": "#/components/schemas/GateProjection"
        },
        "maxItems": 2
      },
      "recommendedPollAfterSeconds": {
        "description": "Minimum client read interval only; never worker cadence or an ETA.",
        "type": [
          "integer",
          "null"
        ],
        "enum": [
          15,
          60,
          null
        ]
      }
    }
  }
};
function schema(name:string):unknown{
 const expand=(value:unknown):unknown=>Array.isArray(value)?value.map(expand):value&&typeof value==="object"?
  typeof (value as {$ref?:unknown}).$ref==="string"?expand(schemas[String((value as {$ref:string}).$ref).split("/").at(-1)!]):Object.fromEntries(Object.entries(value).map(([key,entry])=>[key,expand(entry)])):value;
 return expand(schemas[name]);
}
const common={method:"GET",owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,allowPending:false,successStatuses:[200],request:null} as const;
export const STATUS_ROUTES=[
 {...common,id:"listGroupSubmissionIntents",pathPattern:"/api/v001/group-submission-intents",handler:"status",auth:"installation_bearer",expectedChallenge:'Bearer realm="fga-api"',response:schema("IntentPage")},
 {...common,id:"readGroupSubmissionIntent",pathPattern:"/api/v001/group-submission-intents/{submissionIntentId}",handler:"status",auth:"installation_bearer",expectedChallenge:'Bearer realm="fga-api"',response:schema("IntentItem")},
 {...common,id:"listAdministrativeSubmissionIntents",pathPattern:"/api/v001/admin/group-submission-intents",handler:"status_admin",auth:"browser_session",expectedChallenge:null,response:schema("IntentPage")},
 {...common,id:"readAdministrativeSubmissionIntent",pathPattern:"/api/v001/admin/group-submission-intents/{submissionIntentId}",handler:"status_admin",auth:"browser_session",expectedChallenge:null,response:schema("IntentItem")},
] as const;
