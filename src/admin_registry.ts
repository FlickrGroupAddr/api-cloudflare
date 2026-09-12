const CORE_ADMIN_ROUTES = [
{
  "id": "listAdministrativeSessions",
  "method": "GET",
  "pathPattern": "/api/v001/admin/sessions",
  "owner": "fga_api_backend",
  "routingClass": "worker_first",
  "probe": "missing_authentication",
  "expectedStatus": 401,
  "expectedChallenge": null,
  "handler": "admin",
  "auth": "browser_session",
  "allowPending": false,
  "successStatuses": [
    200
  ],
  "request": null,
  "response": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "sessionSetRevision",
      "sessions",
      "nextPageToken"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "sessionSetRevision": {
        "type": "integer",
        "minimum": 1
      },
      "sessions": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "sessionId",
            "revision",
            "createdAt",
            "recentAuthenticationAt",
            "lastActivityAt",
            "expiresAt",
            "state",
            "revokedAt",
            "isCurrent"
          ],
          "properties": {
            "sessionId": {
              "type": "string",
              "minLength": 1,
              "description": "Opaque identifier; clients do not parse, increment, or derive authority from its spelling."
            },
            "revision": {
              "type": "integer",
              "minimum": 1
            },
            "createdAt": {
              "type": "string",
              "format": "date-time"
            },
            "recentAuthenticationAt": {
              "type": "string",
              "format": "date-time"
            },
            "lastActivityAt": {
              "type": "string",
              "format": "date-time"
            },
            "expiresAt": {
              "type": "string",
              "format": "date-time"
            },
            "state": {
              "type": "string",
              "enum": [
                "active",
                "expired",
                "revoked"
              ]
            },
            "revokedAt": {
              "type": [
                "string",
                "null"
              ],
              "format": "date-time"
            },
            "isCurrent": {
              "type": "boolean"
            }
          }
        },
        "maxItems": 50
      },
      "nextPageToken": {
        "type": [
          "string",
          "null"
        ]
      }
    }
  }
},
{
  "id": "revokeAdministrativeSession",
  "method": "POST",
  "pathPattern": "/api/v001/admin/sessions/{sessionId}/revocation",
  "owner": "fga_api_backend",
  "routingClass": "worker_first",
  "probe": "missing_authentication",
  "expectedStatus": 401,
  "expectedChallenge": null,
  "handler": "admin",
  "auth": "browser_session",
  "allowPending": false,
  "successStatuses": [
    204
  ],
  "request": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "expectedRevision"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "expectedRevision": {
        "type": "integer",
        "minimum": 1
      }
    }
  },
  "response": null
},
{
  "id": "revokeOtherAdministrativeSessions",
  "method": "POST",
  "pathPattern": "/api/v001/admin/sessions/revoke-others",
  "owner": "fga_api_backend",
  "routingClass": "worker_first",
  "probe": "missing_authentication",
  "expectedStatus": 401,
  "expectedChallenge": null,
  "handler": "admin",
  "auth": "browser_session",
  "allowPending": false,
  "successStatuses": [
    204
  ],
  "request": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "schemaVersion",
      "expectedSessionSetRevision",
      "expectedActiveOtherSessionCount"
    ],
    "properties": {
      "schemaVersion": {
        "type": "integer",
        "const": 1
      },
      "expectedSessionSetRevision": {
        "type": "integer",
        "minimum": 1
      },
      "expectedActiveOtherSessionCount": {
        "type": "integer",
        "minimum": 0
      }
    }
  },
  "response": null
},
 {id:"startAdministrativeFlickrAuthorization",method:"POST",pathPattern:"/api/v001/admin/flickr-connection/authorization",owner:"fga_api_backend",routingClass:"worker_first",probe:"missing_authentication",expectedStatus:401,expectedChallenge:null,handler:"admin",auth:"browser_session",allowPending:false,successStatuses:[201],request:{type:"object",additionalProperties:false,required:["schemaVersion","expectedRevision"],properties:{schemaVersion:{const:1},expectedRevision:{type:"integer",minimum:1,maximum:Number.MAX_SAFE_INTEGER}}},response:{type:"object",additionalProperties:false,required:["schemaVersion","authorizationTransactionId","authorizationUrl","expiresAt"],properties:{schemaVersion:{const:1},authorizationTransactionId:{type:"string",format:"uuid"},authorizationUrl:{type:"string",format:"uri"},expiresAt:{type:"string",pattern:"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{6}Z$"}}}},
  {
    "id": "readAdministrativeSession",
    "method": "GET",
    "pathPattern": "/api/v001/admin/session",
    "owner": "fga_api_backend",
    "routingClass": "worker_first",
    "probe": "missing_authentication",
    "expectedStatus": 401,
    "expectedChallenge": null,
    "handler": "admin",
    "auth": "browser_session",
    "allowPending": false,
    "response": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "sessionId",
        "revision",
        "sessionSetRevision",
        "createdAt",
        "recentAuthenticationAt",
        "lastActivityAt",
        "expiresAt",
        "csrfToken"
      ],
      "properties": {
        "schemaVersion": {
          "type": "integer",
          "const": 1
        },
        "sessionId": {
          "type": "string",
          "minLength": 1,
          "description": "Opaque identifier; clients do not parse, increment, or derive authority from its spelling."
        },
        "revision": {
          "type": "integer",
          "minimum": 1
        },
        "sessionSetRevision": {
          "type": "integer",
          "minimum": 1
        },
        "createdAt": {
          "type": "string",
          "format": "date-time"
        },
        "recentAuthenticationAt": {
          "type": "string",
          "format": "date-time"
        },
        "lastActivityAt": {
          "type": "string",
          "format": "date-time"
        },
        "expiresAt": {
          "type": "string",
          "format": "date-time"
        },
        "csrfToken": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_-]{43}$",
          "description": "Canonical RFC 4648 base64url without padding for exactly 256 random bits."
        }
      }
    },
    "successStatuses": [
      200
    ],
    "request": null
  },
  {
    "id": "startAdministrativeSessionReauthentication",
    "method": "POST",
    "pathPattern": "/api/v001/admin/session/reauthentication",
    "owner": "fga_api_backend",
    "routingClass": "worker_first",
    "probe": "missing_authentication",
    "expectedStatus": 401,
    "expectedChallenge": null,
    "handler": "admin",
    "auth": "browser_session",
    "allowPending": false,
    "response": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "state",
        "nonce",
        "expiresAt"
      ],
      "properties": {
        "schemaVersion": {
          "type": "integer",
          "const": 1
        },
        "state": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_-]{43}$",
          "description": "Canonical RFC 4648 base64url without padding for exactly 256 random bits."
        },
        "nonce": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_-]{43}$",
          "description": "Canonical RFC 4648 base64url without padding for exactly 256 random bits."
        },
        "expiresAt": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "successStatuses": [
      201
    ],
    "request": null
  },
  {
    "id": "logoutAdministrativeSession",
    "method": "POST",
    "pathPattern": "/api/v001/admin/session/logout",
    "owner": "fga_api_backend",
    "routingClass": "worker_first",
    "probe": "missing_authentication",
    "expectedStatus": 401,
    "expectedChallenge": null,
    "handler": "admin",
    "auth": "browser_session",
    "allowPending": false,
    "response": null,
    "successStatuses": [
      204
    ],
    "request": null
  },
  {
    "id": "readAdministrativeFlickrConnection",
    "method": "GET",
    "pathPattern": "/api/v001/admin/flickr-connection",
    "owner": "fga_api_backend",
    "routingClass": "worker_first",
    "probe": "missing_authentication",
    "expectedStatus": 401,
    "expectedChallenge": null,
    "handler": "admin",
    "auth": "browser_session",
    "allowPending": false,
    "response": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "revision",
        "state",
        "flickrOwnerNsid",
        "verifiedPermission",
        "verifiedAt",
        "localCredentialState",
        "fgaOperationState",
        "flickrPermissionState",
        "userWriteGate",
        "deploymentWriteGate"
      ],
      "properties": {
        "schemaVersion": {
          "const": 1
        },
        "revision": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "state": {
          "enum": [
            "unlinked",
            "linked",
            "replacing",
            "repair_required",
            "relink_required",
            "disconnecting",
            "disconnected"
          ]
        },
        "flickrOwnerNsid": {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        },
        "verifiedPermission": {
          "enum": [
            "write",
            "delete",
            null
          ]
        },
        "verifiedAt": {
          "oneOf": [
            {
              "type": "string",
              "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$"
            },
            {
              "type": "null"
            }
          ]
        },
        "localCredentialState": {
          "enum": [
            "absent",
            "available",
            "replacement_pending",
            "retirement_pending",
            "retired",
            "unknown"
          ]
        },
        "fgaOperationState": {
          "enum": [
            "enabled",
            "read_only",
            "stopped"
          ]
        },
        "flickrPermissionState": {
          "enum": [
            "not_requested",
            "owner_action_required"
          ]
        },
        "userWriteGate": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "state",
            "revision"
          ],
          "properties": {
            "state": {
              "enum": [
                "enabled",
                "paused"
              ]
            },
            "revision": {
              "type": "integer",
              "minimum": 1,
              "maximum": 9007199254740991
            }
          }
        },
        "deploymentWriteGate": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "state",
            "revision"
          ],
          "properties": {
            "state": {
              "enum": [
                "enabled",
                "paused"
              ]
            },
            "revision": {
              "type": "integer",
              "minimum": 1,
              "maximum": 9007199254740991
            }
          }
        }
      }
    },
    "successStatuses": [
      200
    ],
    "request": null
  },
  {
    "id": "disconnectAdministrativeFlickrConnection",
    "method": "POST",
    "pathPattern": "/api/v001/admin/flickr-connection/disconnection",
    "owner": "fga_api_backend",
    "routingClass": "worker_first",
    "probe": "missing_authentication",
    "expectedStatus": 401,
    "expectedChallenge": null,
    "handler": "admin",
    "auth": "browser_session",
    "allowPending": false,
    "response": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "revision",
        "state",
        "flickrOwnerNsid",
        "verifiedPermission",
        "verifiedAt",
        "localCredentialState",
        "fgaOperationState",
        "flickrPermissionState",
        "userWriteGate",
        "deploymentWriteGate"
      ],
      "properties": {
        "schemaVersion": {
          "const": 1
        },
        "revision": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "state": {
          "enum": [
            "unlinked",
            "linked",
            "replacing",
            "repair_required",
            "relink_required",
            "disconnecting",
            "disconnected"
          ]
        },
        "flickrOwnerNsid": {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        },
        "verifiedPermission": {
          "enum": [
            "write",
            "delete",
            null
          ]
        },
        "verifiedAt": {
          "oneOf": [
            {
              "type": "string",
              "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$"
            },
            {
              "type": "null"
            }
          ]
        },
        "localCredentialState": {
          "enum": [
            "absent",
            "available",
            "replacement_pending",
            "retirement_pending",
            "retired",
            "unknown"
          ]
        },
        "fgaOperationState": {
          "enum": [
            "enabled",
            "read_only",
            "stopped"
          ]
        },
        "flickrPermissionState": {
          "enum": [
            "not_requested",
            "owner_action_required"
          ]
        },
        "userWriteGate": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "state",
            "revision"
          ],
          "properties": {
            "state": {
              "enum": [
                "enabled",
                "paused"
              ]
            },
            "revision": {
              "type": "integer",
              "minimum": 1,
              "maximum": 9007199254740991
            }
          }
        },
        "deploymentWriteGate": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "state",
            "revision"
          ],
          "properties": {
            "state": {
              "enum": [
                "enabled",
                "paused"
              ]
            },
            "revision": {
              "type": "integer",
              "minimum": 1,
              "maximum": 9007199254740991
            }
          }
        }
      }
    },
    "successStatuses": [
      200,
      202
    ],
    "request": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "expectedRevision",
        "expectedFlickrOwnerNsid"
      ],
      "properties": {
        "schemaVersion": {
          "const": 1
        },
        "expectedRevision": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "expectedFlickrOwnerNsid": {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        }
      }
    }
  }
] as const;

export const ADMIN_ROUTES=[...CORE_ADMIN_ROUTES,...(["user","deployment"] as const).map(gate=>({...CORE_ADMIN_ROUTES.find(r=>r.pathPattern==="/api/v001/admin/flickr-connection/disconnection")!,id:"resume_"+gate+"_write_gate",pathPattern:"/api/v001/admin/flickr-write-gates/"+gate+"/resume",successStatuses:[200],request:{type:"object",additionalProperties:false,required:["schemaVersion","expectedRevision"],properties:{schemaVersion:{const:1},expectedRevision:{type:"integer",minimum:1,maximum:Number.MAX_SAFE_INTEGER}}}}))];
