// WHATWG Encoding index, 2024-09-18; Bun 1.3.14 lacks this decoder.
// https://encoding.spec.whatwg.org/index-windows-1251.txt
const WINDOWS_1251 = [
  1026, 1027, 8218, 1107, 8222, 8230, 8224, 8225, 8364, 8240, 1033, 8249, 1034, 1036, 1035, 1039,
  1106, 8216, 8217, 8220, 8221, 8226, 8211, 8212, 152, 8482, 1113, 8250, 1114, 1116, 1115, 1119,
  160, 1038, 1118, 1032, 164, 1168, 166, 167, 1025, 169, 1028, 171, 172, 173, 174, 1031, 176, 177,
  1030, 1110, 1169, 181, 182, 183, 1105, 8470, 1108, 187, 1112, 1029, 1109, 1111, 1040, 1041, 1042,
  1043, 1044, 1045, 1046, 1047, 1048, 1049, 1050, 1051, 1052, 1053, 1054, 1055, 1056, 1057, 1058,
  1059, 1060, 1061, 1062, 1063, 1064, 1065, 1066, 1067, 1068, 1069, 1070, 1071, 1072, 1073, 1074,
  1075, 1076, 1077, 1078, 1079, 1080, 1081, 1082, 1083, 1084, 1085, 1086, 1087, 1088, 1089, 1090,
  1091, 1092, 1093, 1094, 1095, 1096, 1097, 1098, 1099, 1100, 1101, 1102, 1103,
];

export function decodeHttpBody(bytes: Uint8Array, contentType: string): string {
  const charset =
    /charset\s*=\s*["']?([^;\s"']+)/i.exec(contentType)?.[1]?.toLowerCase() ?? "utf-8";
  if (!["cp1251", "windows-1251", "x-cp1251"].includes(charset))
    return new TextDecoder(charset).decode(bytes);
  const characters: string[] = [];
  for (const byte of bytes)
    characters.push(String.fromCharCode(byte < 128 ? byte : WINDOWS_1251[byte - 128]));
  return characters.join("");
}
