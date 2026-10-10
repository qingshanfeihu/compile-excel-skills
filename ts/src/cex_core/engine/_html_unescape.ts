const NAMED: Record<string, string> = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'",
  nbsp: " ", copy: "©", reg: "®", trade: "™",
  hellip: "…", mdash: "—", ndash: "–", lsquo: "‘", rsquo: "’",
  ldquo: "“", rdquo: "”", laquo: "«", raquo: "»",
  times: "×", divide: "÷", minus: "−", deg: "°", plusmn: "±",
  middot: "·", bull: "•", dagger: "†", Dagger: "‡",
  permil: "‰", prime: "′", Prime: "″", euro: "€", pound: "£",
  yen: "¥", cent: "¢", sect: "§", para: "¶", micro: "µ",
  iexcl: "¡", iquest: "¿", szlig: "ß",
  agrave: "à", aacute: "á", acirc: "â", atilde: "ã", auml: "ä", aring: "å", aelig: "æ", ccedil: "ç",
  egrave: "è", eacute: "é", ecirc: "ê", euml: "ë",
  igrave: "ì", iacute: "í", icirc: "î", iuml: "ï", eth: "ð", ntilde: "ñ",
  ograve: "ò", oacute: "ó", ocirc: "ô", otilde: "õ", ouml: "ö", oslash: "ø",
  ugrave: "ù", uacute: "ú", ucirc: "û", uuml: "ü", yacute: "ý", thorn: "þ", yuml: "ÿ",
  Agrave: "À", Aacute: "Á", Acirc: "Â", Atilde: "Ã", Auml: "Ä", Aring: "Å", AElig: "Æ", Ccedil: "Ç",
  Egrave: "È", Eacute: "É", Ecirc: "Ê", Euml: "Ë",
  Igrave: "Ì", Iacute: "Í", Icirc: "Î", Iuml: "Ï", ETH: "Ð", Ntilde: "Ñ",
  Ograve: "Ò", Oacute: "Ó", Ocirc: "Ô", Otilde: "Õ", Ouml: "Ö", Oslash: "Ø",
  Ugrave: "Ù", Uacute: "Ú", Ucirc: "Û", Uuml: "Ü", Yacute: "Ý", THORN: "Þ",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", zeta: "ζ", eta: "η", theta: "θ",
  iota: "ι", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", omicron: "ο", pi: "π",
  rho: "ρ", sigma: "σ", tau: "τ", upsilon: "υ", phi: "φ", chi: "χ", psi: "ψ", omega: "ω",
  Alpha: "Α", Beta: "Β", Gamma: "Γ", Delta: "Δ", Epsilon: "Ε", Zeta: "Ζ", Eta: "Η", Theta: "Θ",
  Iota: "Ι", Kappa: "Κ", Lambda: "Λ", Mu: "Μ", Nu: "Ν", Xi: "Ξ", Omicron: "Ο", Pi: "Π",
  Rho: "Ρ", Sigma: "Σ", Tau: "Τ", Upsilon: "Υ", Phi: "Φ", Chi: "Χ", Psi: "Ψ", Omega: "Ω",
  larr: "←", uarr: "↑", rarr: "→", darr: "↓", harr: "↔",
  forall: "∀", part: "∂", exist: "∃", empty: "∅", nabla: "∇", isin: "∈", notin: "∉",
  prod: "∏", sum: "∑", lowast: "∗", radic: "√", prop: "∝", infin: "∞", ang: "∠",
  and: "∧", or: "∨", cap: "∩", cup: "∪", int: "∫", there4: "∴", sim: "∼", cong: "≅",
  asymp: "≈", ne: "≠", equiv: "≡", le: "≤", ge: "≥", sub: "⊂", sup: "⊃", nsub: "⊄",
  sube: "⊆", supe: "⊇", oplus: "⊕", otimes: "⊗", perp: "⊥", sdot: "⋅",
  lceil: "⌈", rceil: "⌉", lfloor: "⌊", rfloor: "⌋", loz: "◊", spades: "♠", clubs: "♣",
  hearts: "♥", diams: "♦",
};

export function htmlUnescape(text: string): string {
  if (!text || text.indexOf("&") < 0) {
    return text;
  }
  return text.replace(/&(#x[0-9A-Fa-f]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*);?/g, (match, body) => {
    if (body[0] === "#") {
      let code: number;
      if (body[1] === "x" || body[1] === "X") {
        code = parseInt(body.slice(2), 16);
      } else {
        code = parseInt(body.slice(1), 10);
      }
      if (!Number.isFinite(code) || code < 0 || code > 0x10ffff) {
        return match;
      }
      if (code === 0 || (code >= 0xd800 && code <= 0xdfff)) {
        return "";
      }
      try {
        return String.fromCodePoint(code);
      } catch {
        return match;
      }
    }
    const hit = NAMED[body];
    return hit !== undefined ? hit : match;
  });
}
