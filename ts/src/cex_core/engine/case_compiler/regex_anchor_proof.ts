export class RegexAnchorAnalysisUnavailable extends Error {}

export class RegexAnchorAnalysis {
  contradiction: string;
  window_boundary_dependent: boolean;
  constructor(contradiction = "", window_boundary_dependent = false) {
    this.contradiction = contradiction;
    this.window_boundary_dependent = window_boundary_dependent;
    Object.freeze(this);
  }
}

interface _Node {
  op: string;
  value: any;
}

function _parse(pattern: string, flags: number): _Node[] | null {
  // Minimal Python-regex subset parser: enough for AT/SUBPATTERN/BRANCH/REPEAT/ATOMIC_GROUP structure.
  // Falls back to null on parse failure (callers treat as "no contradiction provable").
  try {
    const nodes: _Node[] = [];
    let i = 0;
    const n = pattern.length;
    const parseGroup = (): _Node[] => {
      const out: _Node[] = [];
      while (i < n) {
        const c = pattern[i];
        if (c === ")") return out;
        if (c === "|") {
          // branch handled by caller
          return out;
        }
        if (c === "^") {
          out.push({ op: "AT", value: flags & 8 ? "AT_BEGINNING" : "AT_BEGINNING_STRING" });
          i++;
          continue;
        }
        if (c === "$") {
          out.push({ op: "AT", value: flags & 8 ? "AT_END" : "AT_END" });
          i++;
          continue;
        }
        if (c === "\\") {
          if (i + 1 < n) {
            out.push({ op: "LITERAL", value: pattern.slice(i, i + 2) });
            i += 2;
          } else {
            i++;
          }
          continue;
        }
        if (c === "(") {
          i++;
          let child: _Node[];
          if (pattern.startsWith("?:", i)) {
            i += 2;
            child = parseGroup();
          } else if (pattern.startsWith("?P<", i)) {
            const end = pattern.indexOf(">", i);
            i = end + 1;
            child = parseGroup();
          } else if (pattern.startsWith("?", i)) {
            const end = pattern.indexOf(":", i);
            i = end + 1;
            child = parseGroup();
          } else {
            child = parseGroup();
          }
          if (pattern[i] === ")") i++;
          out.push({ op: "SUBPATTERN", value: child });
          continue;
        }
        if (c === "[" ) {
          let j = i + 1;
          if (pattern[j] === "^") j++;
          if (pattern[j] === "]") j++;
          while (j < n && pattern[j] !== "]") {
            if (pattern[j] === "\\") j++;
            j++;
          }
          out.push({ op: "IN", value: pattern.slice(i, j + 1) });
          i = j + 1;
          continue;
        }
        if (c === "*" || c === "+" || c === "?" ) {
          out.push({ op: "MAX_REPEAT", value: { min: c === "+" ? 1 : 0, child: out.pop()! } });
          i++;
          continue;
        }
        if (c === "{") {
          const m = /^\{(\d+)(?:,(\d*)?)?\}/.exec(pattern.slice(i));
          if (m) {
            const min = parseInt(m[1], 10);
            const child = out.pop()!;
            out.push({ op: "MAX_REPEAT", value: { min, child } });
            i += m[0].length;
            continue;
          }
        }
        out.push({ op: "LITERAL", value: c });
        i++;
      }
      return out;
    };
    // top-level with branches
    const branches: _Node[][] = [];
    let cur: _Node[] = [];
    while (i < n) {
      const before = i;
      const parsed = parseGroup();
      if (i === before) break;
      cur = cur.concat(parsed);
      if (pattern[i] === "|") {
        branches.push(cur);
        cur = [];
        i++;
      }
    }
    branches.push(cur);
    nodes.push(...(branches.length > 1 ? [{ op: "BRANCH", value: branches }] : branches[0]));
    return nodes;
  } catch {
    return null;
  }
}

function _minWidth(node: _Node): number {
  switch (node.op) {
    case "AT": return 0;
    case "LITERAL": return 1;
    case "IN": return 1;
    case "SUBPATTERN": return (node.value as _Node[]).reduce((a, x) => a + _minWidth(x), 0);
    case "BRANCH": return Math.min(...(node.value as _Node[][]).map((b) => b.reduce((a, x) => a + _minWidth(x), 0)));
    case "MAX_REPEAT": return (node.value.min as number) * _minWidth(node.value.child as _Node);
    default: return 1;
  }
}

export function analyze_regex_anchors(pattern: string, flags = 4): RegexAnchorAnalysis {
  const tree = _parse(pattern, flags);
  if (tree === null) {
    return new RegexAnchorAnalysis();
  }
  let visited = 0;
  let boundaryDependent = false;

  const prove = (nodes: _Node[], effectiveFlags: number, before: number, after: number, depth: number): string => {
    visited += nodes.length;
    if (visited > 4096 || depth > 128) {
      throw new RegexAnchorAnalysisUnavailable("regex tree exceeds the analysis boundary");
    }
    const widths = nodes.map((item) => _minWidth(item));
    let remaining = widths.reduce((a, b) => a + b, 0);
    let prefix = before;
    for (let idx = 0; idx < nodes.length; idx++) {
      const node = nodes[idx];
      const width = widths[idx];
      remaining -= width;
      const suffix = after + remaining;
      let proof = "";
      if (node.op === "AT") {
        const value = node.value;
        const start = value === "AT_BEGINNING_STRING" || (value === "AT_BEGINNING" && !(effectiveFlags & 8));
        const absoluteEnd = value === "AT_END_STRING";
        const softEnd = value === "AT_END" && !(effectiveFlags & 8);
        boundaryDependent = boundaryDependent || start || absoluteEnd || softEnd;
        if (start && prefix > 0) {
          proof = "a string-start anchor follows a mandatory non-empty prefix";
        } else if (absoluteEnd && suffix > 0) {
          proof = "a mandatory non-empty suffix follows a string-end anchor";
        } else if (softEnd && suffix > 1) {
          proof = "more than one mandatory character follows an end anchor";
        }
      } else if (node.op === "SUBPATTERN") {
        proof = prove(node.value, effectiveFlags, prefix, suffix, depth + 1);
      } else if (node.op === "BRANCH") {
        const branches = (node.value as _Node[][]).map((child) => prove(child, effectiveFlags, prefix, suffix, depth + 1));
        if (branches.length && branches.every(Boolean)) {
          proof = "every alternative contains an incompatible string-boundary anchor";
        }
      } else if (node.op === "MAX_REPEAT") {
        if ((node.value.min as number) > 0) {
          proof = prove([node.value.child], effectiveFlags, prefix, suffix, depth + 1);
        }
      }
      if (proof) {
        return proof;
      }
      prefix += width;
    }
    return "";
  };
  const contradiction = prove(tree, flags, 0, 0, 0);
  return new RegexAnchorAnalysis(contradiction, boundaryDependent);
}
