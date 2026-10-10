// 生成：tools/extract_engine.py ← InfoTest scripts/gen_package_advisories.py（sha256 629f71d83701254f）。不在这里手改。
import { write_package_advisories } from "./maintenance/build_package_advisories";

export function main(): number {
  return write_package_advisories();
}

if (require.main === module) {
  process.exit(main());
}
