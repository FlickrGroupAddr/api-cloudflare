import { AwsClient } from "aws4fetch";
import { ProbeError, type Transport } from "./client.ts";

export interface Credentials {
  AccessKeyId: string;
  SecretAccessKey: string;
  SessionToken: string;
  Expiration: string;
}

export function signedTransport(
  credentials: Credentials, region: string, send: Transport,
): Transport {
  return async (request) => {
    if (!credentials.AccessKeyId || !credentials.SecretAccessKey || !credentials.SessionToken ||
      !Number.isFinite(Date.parse(credentials.Expiration)) ||
      Date.parse(credentials.Expiration) <= Date.now() + 15_000 ||
      request.url !== `https://secretsmanager.${region}.amazonaws.com/` ||
      request.method !== "POST" || request.redirect !== "manual") {
      throw new ProbeError("invalid_input");
    }
    const client = new AwsClient({
      accessKeyId: credentials.AccessKeyId,
      secretAccessKey: credentials.SecretAccessKey,
      sessionToken: credentials.SessionToken,
      region, service: "secretsmanager", retries: 0,
    });
    try {
      // Only sign: the library's implicit retries and global fetch are not used.
      const signed = await client.sign(request);
      // workerd rejects redirect:"error". Manual mode prevents credentials from
      // reaching another endpoint; reject redirects without following Location.
      const reply = await send(new Request(signed, { redirect: "manual", signal: request.signal }));
      if (reply.redirected || (reply.status >= 300 && reply.status < 400)) {
        void reply.body?.cancel().catch(() => {});
        throw new ProbeError("transport");
      }
      return reply;
    } catch {
      throw new ProbeError("transport");
    }
  };
}
