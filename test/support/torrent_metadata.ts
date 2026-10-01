// Structural metainfo checks based on BEP 3 and BEP 52:
// https://www.bittorrent.org/beps/bep_0003.html
// https://www.bittorrent.org/beps/bep_0052.html
type Value = number | Uint8Array | Value[] | Map<string, Value>;

export function assertTorrentMetadata(bytes: Uint8Array): void {
  if (!bytes.length || bytes.length > 4 * 1024 * 1024) throw new Error("invalid metainfo size");
  let position = 0;
  let nodes = 0;
  const fail = (): never => {
    throw new Error("invalid bencoded torrent metadata");
  };
  const parse = (depth: number): Value => {
    if (depth > 100 || ++nodes > 100_000 || position >= bytes.length) return fail();
    const kind = bytes[position];
    if (kind >= 48 && kind <= 57) {
      const colon = bytes.indexOf(58, position);
      if (colon < 0 || colon - position > 10) return fail();
      const digits = Buffer.from(bytes.subarray(position, colon)).toString("latin1");
      if (!/^(?:0|[1-9]\d*)$/.test(digits)) return fail();
      const length = Number(digits);
      position = colon + 1;
      if (!Number.isSafeInteger(length) || position + length > bytes.length) return fail();
      const value = bytes.subarray(position, position + length);
      position += length;
      return value;
    }
    position += 1;
    if (kind === 105) {
      const end = bytes.indexOf(101, position);
      if (end < 0 || end - position > 20) return fail();
      const digits = Buffer.from(bytes.subarray(position, end)).toString("latin1");
      if (!/^(?:0|-?[1-9]\d*)$/.test(digits)) return fail();
      const number = Number(digits);
      if (!Number.isSafeInteger(number)) return fail();
      position = end + 1;
      return number;
    }
    if (kind === 108) {
      const list: Value[] = [];
      while (bytes[position] !== 101) list.push(parse(depth + 1));
      position += 1;
      return list;
    }
    if (kind === 100) {
      const dict = new Map<string, Value>();
      let previous: Uint8Array | undefined;
      while (bytes[position] !== 101) {
        const key = parse(depth + 1);
        if (!(key instanceof Uint8Array) || (previous && Buffer.compare(previous, key) >= 0))
          return fail();
        previous = key;
        dict.set(Buffer.from(key).toString("latin1"), parse(depth + 1));
      }
      position += 1;
      return dict;
    }
    return fail();
  };
  const nonnegative = (value: Value | undefined): value is number =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  const text = (value: Value | undefined): value is Uint8Array =>
    value instanceof Uint8Array && value.length > 0;
  const root = parse(0);
  if (position !== bytes.length || !(root instanceof Map)) return fail();
  const info = root.get("info");
  if (!(info instanceof Map) || !text(info.get("name"))) return fail();
  const pieceLength = info.get("piece length");
  if (!nonnegative(pieceLength) || pieceLength === 0) return fail();
  const pieces = info.get("pieces");
  if (pieces !== undefined) {
    if (!(pieces instanceof Uint8Array) || pieces.length % 20 !== 0) return fail();
    let size = 0;
    const length = info.get("length");
    const files = info.get("files");
    if ((length === undefined) === (files === undefined)) return fail();
    if (length !== undefined) {
      if (!nonnegative(length)) return fail();
      size = length;
    } else {
      if (!Array.isArray(files) || !files.length) return fail();
      for (const file of files) {
        if (!(file instanceof Map)) return fail();
        const fileLength = file.get("length");
        const path = file.get("path");
        if (!nonnegative(fileLength) || !Array.isArray(path) || !path.length || !path.every(text))
          return fail();
        size += fileLength;
      }
    }
    if (!Number.isSafeInteger(size) || pieces.length / 20 !== Math.ceil(size / pieceLength))
      return fail();
  } else if (info.get("meta version") !== 2) return fail();
  if (info.has("meta version")) {
    if (
      info.get("meta version") !== 2 ||
      pieceLength < 16_384 ||
      !Number.isInteger(Math.log2(pieceLength))
    )
      return fail();
    const tree = info.get("file tree");
    if (!(tree instanceof Map) || !tree.size) return fail();
    let files = 0;
    const walk = (branch: Map<string, Value>, depth: number): void => {
      if (depth > 100 || !branch.size) return fail();
      for (const [name, node] of branch) {
        if (!(node instanceof Map)) return fail();
        if (name === "") {
          if (depth === 0 || branch.size !== 1) return fail();
          const length = node.get("length");
          if (!nonnegative(length)) return fail();
          const hash = node.get("pieces root");
          if (length > 0 && (!(hash instanceof Uint8Array) || hash.length !== 32)) return fail();
          if (length > pieceLength) {
            const layers = root.get("piece layers");
            const layer =
              layers instanceof Map && hash instanceof Uint8Array
                ? layers.get(Buffer.from(hash).toString("latin1"))
                : undefined;
            if (
              !(layer instanceof Uint8Array) ||
              layer.length !== Math.ceil(length / pieceLength) * 32
            )
              return fail();
          }
          files += 1;
        } else walk(node, depth + 1);
      }
    };
    walk(tree, 0);
    if (!files) return fail();
  }
}
