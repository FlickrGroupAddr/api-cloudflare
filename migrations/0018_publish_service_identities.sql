-- Immutable, retained identities. No album, provider side effect or idempotency key.
CREATE TABLE publish_service_identities (
 service_id TEXT PRIMARY KEY NOT NULL CHECK(length(service_id)=36 AND service_id=lower(service_id)
  AND service_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(service_id,'-',''))=32 AND replace(service_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 issuing_installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 link_revision INTEGER NOT NULL CHECK(link_revision BETWEEN 1 AND 9007199254740991),
 owner_nsid TEXT NOT NULL CHECK(length(owner_nsid) BETWEEN 1 AND 128),
 service_revision INTEGER NOT NULL DEFAULT 1 CHECK(service_revision=1)
) STRICT;
CREATE TRIGGER publish_service_no_update BEFORE UPDATE ON publish_service_identities
 BEGIN SELECT RAISE(ABORT,'publish_service_immutable'); END;
CREATE TRIGGER publish_service_no_delete BEFORE DELETE ON publish_service_identities
 BEGIN SELECT RAISE(ABORT,'publish_service_retained'); END;
CREATE TRIGGER publish_service_no_replace BEFORE INSERT ON publish_service_identities
 WHEN EXISTS(SELECT 1 FROM publish_service_identities WHERE service_id=NEW.service_id)
 BEGIN SELECT RAISE(ABORT,'publish_service_retained'); END;
