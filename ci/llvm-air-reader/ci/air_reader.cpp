// SPDX-License-Identifier: GPL-3.0-or-later
// iDeck native-host compatibility probe. No Metal/GPU/MSC/JIT API is called.
#include "llvm/Bitcode/BitcodeReader.h"
#include "llvm/Config/llvm-config.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/Support/Error.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/raw_ostream.h"
#include <string>
#include <vector>

static_assert(LLVM_VERSION_MAJOR == 15 && LLVM_VERSION_MINOR == 0 &&
              LLVM_VERSION_PATCH == 7, "Exact LLVM 15.0.7 required");

static void quoted(llvm::raw_ostream &out, llvm::StringRef s) {
  constexpr char hex[] = "0123456789abcdef";
  out << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') out << '\\' << char(c);
    else if (c < 0x20 || c >= 0x7f)
      out << "\\u00" << hex[c >> 4] << hex[c & 15];
    else out << char(c);
  }
  out << '"';
}

static std::vector<std::string> required(llvm::StringRef id) {
  if (id == "air_msad") return {"dxmt.msad.i32", "dxmt.msad.v2i32",
    "dxmt.msad.v3i32", "dxmt.msad.v4i32"};
  if (id == "air_samplepos") return {"dxmt.sample_pos.i32"};
  if (id == "air_tessellation") return {
    "dxmt.generate_workload.triangle.integer", "dxmt.generate_workload.triangle.pow2",
    "dxmt.generate_workload.triangle.odd", "dxmt.generate_workload.triangle.even",
    "dxmt.generate_workload.quad.integer", "dxmt.generate_workload.quad.pow2",
    "dxmt.generate_workload.quad.odd", "dxmt.generate_workload.quad.even",
    "dxmt.get_domain_patch_index", "dxmt.get_domain_location.integer",
    "dxmt.get_domain_location.pow2", "dxmt.get_domain_location.odd",
    "dxmt.get_domain_location.even", "dxmt.domain_generate_primitives.triangle",
    "dxmt.domain_generate_primitives.triangle_ccw", "dxmt.domain_generate_primitives.point"};
  return {};
}

int main(int argc, char **argv) {
  if (argc != 3 || required(argv[1]).empty()) {
    llvm::errs() << "usage: llvm15-air-reader air_{msad,samplepos,tessellation} FILE\n";
    return 2;
  }
  auto input = llvm::MemoryBuffer::getFile(argv[2], false, false);
  if (!input) {
    llvm::errs() << "read failed: " << input.getError().message() << '\n';
    return 3;
  }
  if ((*input)->getBufferSize() < 4 || (*input)->getBufferSize() > 32 * 1024 * 1024) {
    llvm::errs() << "AIR byte count outside bound\n";
    return 3;
  }
  // Match DXMT linkShader's MemoryBuffer copy and eager parse. In particular,
  // do not substitute getBitcodeTargetTriple, strings, llvm-dis or a magic check.
  auto buffer = llvm::MemoryBuffer::getMemBufferCopy((*input)->getBuffer());
  llvm::LLVMContext context;
  auto parsed = llvm::parseBitcodeFile(buffer->getMemBufferRef(), context);
  if (!parsed) {
    llvm::errs() << "LLVM15 parseBitcodeFile failed for " << argv[1] << ": "
                 << llvm::toString(parsed.takeError()) << '\n';
    return 4;
  }
  llvm::Module &m = **parsed;
  const std::string source = m.getSourceFileName();
  const std::string basename = source.substr(source.find_last_of("/\\") + 1);
  if (basename != std::string(argv[1]) + ".metal") {
    llvm::errs() << "Unexpected AIR source filename: " << source << '\n';
    return 5;
  }
  const std::string triple = m.getTargetTriple();
  if (triple != "air64-apple-macosx14.0.0" && triple != "air64-apple-macos14.0.0" &&
      triple != "air64-apple-macosx14.0" && triple != "air64-apple-macos14.0") {
    llvm::errs() << "Unexpected AIR target triple: " << triple << '\n';
    return 6;
  }
  const auto names = required(argv[1]);
  for (const auto &name : names) {
    auto *fn = m.getFunction(name);
    if (!fn || fn->isDeclaration() || !fn->hasExternalLinkage()) {
      llvm::errs() << "Missing external function definition: " << name << '\n';
      return 7;
    }
  }
  auto &out = llvm::outs();
  out << "{\"schema\":1,\"status\":\"parsed\",\"llvm_version\":\"15.0.7\",\"id\":";
  quoted(out, argv[1]);
  out << ",\"input_bytes\":" << (*input)->getBufferSize() << ",\"module_identifier\":";
  quoted(out, m.getModuleIdentifier());
  out << ",\"source_filename\":"; quoted(out, source);
  out << ",\"target_triple\":"; quoted(out, triple);
  out << ",\"data_layout\":"; quoted(out, m.getDataLayoutStr());
  out << ",\"functions\":[";
  bool first = true;
  for (const auto &name : names) {
    auto *fn = m.getFunction(name);
    if (!first) out << ',';
    first = false;
    std::string type;
    llvm::raw_string_ostream typeout(type);
    fn->getFunctionType()->print(typeout);
    out << "{\"name\":"; quoted(out, name);
    out << ",\"type\":"; quoted(out, typeout.str());
    out << ",\"declaration\":false,\"external_linkage\":true,\"basic_blocks\":"
        << fn->size() << '}';
  }
  out << "],\"linker_run\":false,\"gpu_run\":false,\"target_executed\":false}\n";
  return 0;
}
