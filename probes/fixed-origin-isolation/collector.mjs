// Discard bodies at the collection boundary. Receipts contain finite labels and lengths only.
export async function collectResponse(response) {
  const limit = response.status === 200 ? 262144 : 4096;
  let observedBytes = 0;
  const reader = response.body?.getReader();
  try {
    if (reader) for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      observedBytes += value.byteLength;
      if (observedBytes > limit) {
        await reader.cancel().catch(() => {});
        return Object.freeze({ status: response.status, observedBytes, limit, accepted: false });
      }
    }
    return Object.freeze({ status: response.status, observedBytes, limit, accepted: true });
  } finally { reader?.releaseLock(); }
}
