-- Retain only proven issuance context. Legacy authorizations deliberately remain NULL.
ALTER TABLE upload_authorizations ADD COLUMN owner_nsid TEXT CHECK(owner_nsid IS NULL OR length(owner_nsid) BETWEEN 1 AND 128);
ALTER TABLE upload_authorizations ADD COLUMN link_revision INTEGER CHECK(link_revision IS NULL OR link_revision BETWEEN 1 AND 9007199254740991);
CREATE TRIGGER upload_authorization_candidate_initial BEFORE INSERT ON upload_authorizations
 WHEN (NEW.owner_nsid IS NULL)<>(NEW.link_revision IS NULL)
   OR (NEW.owner_nsid IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_links l
     WHERE l.user_id=NEW.user_id AND l.state='linked' AND l.owner_nsid=NEW.owner_nsid AND l.link_revision=NEW.link_revision))
 BEGIN SELECT RAISE(ABORT,'upload_authorization_candidate_initial'); END;
CREATE TRIGGER upload_authorization_candidate_identity BEFORE UPDATE ON upload_authorizations
 WHEN NEW.owner_nsid IS NOT OLD.owner_nsid OR NEW.link_revision IS NOT OLD.link_revision
 BEGIN SELECT RAISE(ABORT,'upload_authorization_candidate_identity'); END;
