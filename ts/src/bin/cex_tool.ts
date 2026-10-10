#!/usr/bin/env node
import fs from "node:fs";
import * as tools from "../cex_client/tools";

function readStdin(): string {
  return fs.readFileSync(0, "utf8");
}

function main(argv: string[]): number {
  if (!argv.length || argv[0] === "-h" || argv[0] === "--help") {
    console.log("usage: cex_tool list | <name> - | <name> '<json>' | <name> --args-file F");
    return 2;
  }
  if (argv[0] === "list") {
    console.log(JSON.stringify(tools.loadSpecs(), null, 1));
    return 0;
  }
  const name = argv[0];
  const rest = argv.slice(1);
  let args: any;
  try {
    if (rest[0] === "--args-file" && rest.length === 2) {
      args = JSON.parse(fs.readFileSync(rest[1], "utf8"));
    } else if (rest.length === 1 && rest[0] === "-") {
      args = JSON.parse(readStdin() || "{}");
    } else if (rest.length === 1) {
      args = JSON.parse(rest[0]);
    } else if (rest.length === 0) {
      args = {};
    } else {
      console.error("usage: cex_tool <name> - | ['<json>'] | --args-file F");
      return 2;
    }
  } catch (exc: any) {
    console.log(JSON.stringify({ ok: false, error: `bad arguments: ${exc.message || exc}` }));
    return 2;
  }
  Promise.resolve(tools.call(name, args))
    .then((result: any) => {
      console.log(JSON.stringify(result, null, 1));
      process.exit(result.ok !== false || result.pending ? 0 : 1);
    })
    .catch((exc: any) => {
      console.log(JSON.stringify({ ok: false, error: String(exc && exc.message ? exc.message : exc) }));
      process.exit(1);
    });
  return 0;
}

main(process.argv.slice(2));

