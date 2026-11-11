// Round storage: the real Space bridge, never localStorage. Stable IDs make retry create-only.
export function scoreStore(space) {
  if (!space) throw new Error('Open this reference in the supplied sandbox harness or Living Spaces.');
  const field = (r, k) => space.field(r, k);
  return {
    field,
    async list() {
      const rows = await space.query('rounds', {limit: 500});
      return rows.filter(r => Number.isSafeInteger(field(r,'turns')) && field(r,'turns') >= 6 && Number.isFinite(field(r,'seconds')) && !Number.isNaN(Date.parse(field(r,'finished_at'))));
    },
    async save(draft) {
      try { await space.put('rounds', draft.id, draft.data, {baseRev: 0}); }
      catch(e) { if(e.code !== 'conflict') throw e; }
      // A successful reply is not enough: confirm the exact stored round before celebrating a save.
      const confirmed = await space.get('rounds', draft.id);
      if (!confirmed || Object.keys(draft.data).some(k => field(confirmed,k) !== draft.data[k])) throw Error('Round readback did not match');
      return confirmed;
    }
  };
}
