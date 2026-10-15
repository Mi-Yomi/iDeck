// Own compile-only ABI probe. No main, constructor, target execution or link.
// The same source is compiled as C++ for producer and Objective-C++ for consumer.
#include <FEXCore/Debug/InternalThreadState.h>
#include <FEXCore/Config/Config.h>
#include <cstddef>
#include <cstdint>
#include <type_traits>
#if !defined(__APPLE__) || !defined(__aarch64__)
#error Requires actual Apple arm64 target builtins
#endif
#if !defined(ARCHITECTURE_arm64) || ARCHITECTURE_arm64 != 1 || !defined(NDEBUG)
#error Requires original native FEX architecture and Release inline contract
#endif
#if defined(ARCHITECTURE_arm64ec) || defined(ARCHITECTURE_x86_64) || defined(FEX_IOS_HOST) || defined(_WIN32) || defined(GLIBC_ALLOCATOR_FAULT) || defined(ASSERTIONS_ENABLED) || defined(FEX_DISABLE_TELEMETRY) || defined(ENABLE_GUEST_WINDOW) || defined(FEX_GUEST_WINDOW) || defined(FEX_STEAM_SUPPORT)
#error Unexpected native-FEX incompatible feature macro
#endif
static_assert(std::is_standard_layout_v<FEXCore::UncheckedLongJump::JumpBuf>);
static_assert(std::is_standard_layout_v<FEXCore::Core::InternalThreadState>);
static_assert(std::is_standard_layout_v<FEXCore::Core::CpuStateFrame>);
static_assert(std::is_standard_layout_v<FEXCore::Core::CPUState>);
static_assert(std::is_standard_layout_v<FEXCore::Core::JITPointers>);
static_assert(std::is_standard_layout_v<FEXCore::Core::CPUState::gdt_segment>);
static_assert(std::is_standard_layout_v<FEXCore::Core::UnalignedExclusiveStore>);
static_assert((1) == 1ULL, "schema");
static_assert((sizeof(void*)) == 8ULL, "pointer_size");
static_assert((FEXCore::Utils::FEX_PAGE_SIZE) == 4096ULL, "FEX_PAGE_SIZE");
static_assert((sizeof(FEXCore::UncheckedLongJump::JumpBuf)) == 168ULL, "JumpBuf.sizeof");
static_assert((alignof(FEXCore::UncheckedLongJump::JumpBuf)) == 8ULL, "JumpBuf.alignof");
static_assert((sizeof(FEXCore::Core::CPUState::gdt_segment)) == 8ULL, "gdt_segment.sizeof");
static_assert((sizeof(FEXCore::UncheckedLongJump::JumpBuf::Registers) / sizeof(uint64_t)) == 21ULL, "JumpBuf.register_count");
static_assert((sizeof(FEXCore::Core::InternalThreadState::InterruptFaultPage)) == 4096ULL, "InternalThreadState.InterruptFaultPage.sizeof");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_MULTIBLOCK)) == 0ULL, "CONFIG_MULTIBLOCK");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_MAXINST)) == 1ULL, "CONFIG_MAXINST");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLECODECACHINGWIP)) == 2ULL, "CONFIG_ENABLECODECACHINGWIP");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLELAZYCODECACHINGWIP)) == 3ULL, "CONFIG_ENABLELAZYCODECACHINGWIP");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLECODECACHEVALIDATION)) == 4ULL, "CONFIG_ENABLECODECACHEVALIDATION");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_HOSTFEATURES)) == 5ULL, "CONFIG_HOSTFEATURES");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_SMALLTSCSCALE)) == 6ULL, "CONFIG_SMALLTSCSCALE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_HIDEHYBRID)) == 7ULL, "CONFIG_HIDEHYBRID");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_CPUFEATUREREGISTERS)) == 8ULL, "CONFIG_CPUFEATUREREGISTERS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ROOTFS)) == 9ULL, "CONFIG_ROOTFS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKHOSTLIBS)) == 10ULL, "CONFIG_THUNKHOSTLIBS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKGUESTLIBS)) == 11ULL, "CONFIG_THUNKGUESTLIBS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKCONFIG)) == 12ULL, "CONFIG_THUNKCONFIG");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ENV)) == 13ULL, "CONFIG_ENV");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_HOSTENV)) == 14ULL, "CONFIG_HOSTENV");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ADDITIONALARGUMENTS)) == 15ULL, "CONFIG_ADDITIONALARGUMENTS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLEL2CACHE)) == 16ULL, "CONFIG_DISABLEL2CACHE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHE)) == 17ULL, "CONFIG_DYNAMICL1CACHE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHEINCREASECOUNTHEURISTIC)) == 18ULL, "CONFIG_DYNAMICL1CACHEINCREASECOUNTHEURISTIC");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHEDECREASECOUNTHEURISTIC)) == 19ULL, "CONFIG_DYNAMICL1CACHEDECREASECOUNTHEURISTIC");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_SINGLESTEP)) == 20ULL, "CONFIG_SINGLESTEP");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_GDBSERVER)) == 21ULL, "CONFIG_GDBSERVER");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DUMPIR)) == 22ULL, "CONFIG_DUMPIR");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_PASSMANAGERDUMPIR)) == 23ULL, "CONFIG_PASSMANAGERDUMPIR");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DUMPGPRS)) == 24ULL, "CONFIG_DUMPGPRS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_O0)) == 25ULL, "CONFIG_O0");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_GLOBALJITNAMING)) == 26ULL, "CONFIG_GLOBALJITNAMING");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_LIBRARYJITNAMING)) == 27ULL, "CONFIG_LIBRARYJITNAMING");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_BLOCKJITNAMING)) == 28ULL, "CONFIG_BLOCKJITNAMING");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_GDBSYMBOLS)) == 29ULL, "CONFIG_GDBSYMBOLS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_INJECTLIBSEGFAULT)) == 30ULL, "CONFIG_INJECTLIBSEGFAULT");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DISASSEMBLE)) == 31ULL, "CONFIG_DISASSEMBLE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_X86DISASSEMBLE)) == 32ULL, "CONFIG_X86DISASSEMBLE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_FORCESVEWIDTH)) == 33ULL, "CONFIG_FORCESVEWIDTH");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLETELEMETRY)) == 34ULL, "CONFIG_DISABLETELEMETRY");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_SILENTLOG)) == 35ULL, "CONFIG_SILENTLOG");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_OUTPUTLOG)) == 36ULL, "CONFIG_OUTPUTLOG");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_TELEMETRYDIRECTORY)) == 37ULL, "CONFIG_TELEMETRYDIRECTORY");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_PROFILESTATS)) == 38ULL, "CONFIG_PROFILESTATS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLEGPUVISPROFILING)) == 39ULL, "CONFIG_ENABLEGPUVISPROFILING");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_SMCCHECKS)) == 40ULL, "CONFIG_SMCCHECKS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_TSOENABLED)) == 41ULL, "CONFIG_TSOENABLED");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_VECTORTSOENABLED)) == 42ULL, "CONFIG_VECTORTSOENABLED");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_MEMCPYSETTSOENABLED)) == 43ULL, "CONFIG_MEMCPYSETTSOENABLED");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_HALFBARRIERTSOENABLED)) == 44ULL, "CONFIG_HALFBARRIERTSOENABLED");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_STRICTINPROCESSSPLITLOCKS)) == 45ULL, "CONFIG_STRICTINPROCESSSPLITLOCKS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_KERNELUNALIGNEDATOMICBACKPATCHING)) == 46ULL, "CONFIG_KERNELUNALIGNEDATOMICBACKPATCHING");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_VOLATILEMETADATA)) == 47ULL, "CONFIG_VOLATILEMETADATA");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_X87REDUCEDPRECISION)) == 48ULL, "CONFIG_X87REDUCEDPRECISION");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_STALLPROCESS)) == 49ULL, "CONFIG_STALLPROCESS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_HIDEHYPERVISORBIT)) == 50ULL, "CONFIG_HIDEHYPERVISORBIT");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_STARTUPSLEEP)) == 51ULL, "CONFIG_STARTUPSLEEP");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_STARTUPSLEEPPROCNAME)) == 52ULL, "CONFIG_STARTUPSLEEPPROCNAME");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_MONOHACKS)) == 53ULL, "CONFIG_MONOHACKS");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_SERVERSOCKETPATH)) == 54ULL, "CONFIG_SERVERSOCKETPATH");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_NEEDSSECCOMP)) == 55ULL, "CONFIG_NEEDSSECCOMP");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_EXTENDEDVOLATILEMETADATA)) == 56ULL, "CONFIG_EXTENDEDVOLATILEMETADATA");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_INTERPRETER_INSTALLED)) == 57ULL, "CONFIG_INTERPRETER_INSTALLED");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_APP_FILENAME)) == 58ULL, "CONFIG_APP_FILENAME");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_APP_CONFIG_NAME)) == 59ULL, "CONFIG_APP_CONFIG_NAME");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_IS64BIT_MODE)) == 60ULL, "CONFIG_IS64BIT_MODE");
static_assert((static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLE_VIXL_INDIRECT_RUNTIME_CALLS)) == 61ULL, "CONFIG_DISABLE_VIXL_INDIRECT_RUNTIME_CALLS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::OFF)) == 0ULL, "HostFeatures.OFF");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESVE)) == 1ULL, "HostFeatures.ENABLESVE");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESVE)) == 2ULL, "HostFeatures.DISABLESVE");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEAVX)) == 4ULL, "HostFeatures.ENABLEAVX");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEAVX)) == 8ULL, "HostFeatures.DISABLEAVX");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEAFP)) == 16ULL, "HostFeatures.ENABLEAFP");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEAFP)) == 32ULL, "HostFeatures.DISABLEAFP");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLELRCPC)) == 64ULL, "HostFeatures.ENABLELRCPC");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLELRCPC)) == 128ULL, "HostFeatures.DISABLELRCPC");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLELRCPC2)) == 256ULL, "HostFeatures.ENABLELRCPC2");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLELRCPC2)) == 512ULL, "HostFeatures.DISABLELRCPC2");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECSSC)) == 1024ULL, "HostFeatures.ENABLECSSC");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECSSC)) == 2048ULL, "HostFeatures.DISABLECSSC");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEPMULL128)) == 4096ULL, "HostFeatures.ENABLEPMULL128");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEPMULL128)) == 8192ULL, "HostFeatures.DISABLEPMULL128");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLERNG)) == 16384ULL, "HostFeatures.ENABLERNG");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLERNG)) == 32768ULL, "HostFeatures.DISABLERNG");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECLZERO)) == 65536ULL, "HostFeatures.ENABLECLZERO");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECLZERO)) == 131072ULL, "HostFeatures.DISABLECLZERO");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEATOMICS)) == 262144ULL, "HostFeatures.ENABLEATOMICS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEATOMICS)) == 524288ULL, "HostFeatures.DISABLEATOMICS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFCMA)) == 1048576ULL, "HostFeatures.ENABLEFCMA");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFCMA)) == 2097152ULL, "HostFeatures.DISABLEFCMA");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFLAGM)) == 4194304ULL, "HostFeatures.ENABLEFLAGM");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFLAGM)) == 8388608ULL, "HostFeatures.DISABLEFLAGM");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFLAGM2)) == 16777216ULL, "HostFeatures.ENABLEFLAGM2");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFLAGM2)) == 33554432ULL, "HostFeatures.DISABLEFLAGM2");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFRINTTS)) == 67108864ULL, "HostFeatures.ENABLEFRINTTS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFRINTTS)) == 134217728ULL, "HostFeatures.DISABLEFRINTTS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECRYPTO)) == 268435456ULL, "HostFeatures.ENABLECRYPTO");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECRYPTO)) == 536870912ULL, "HostFeatures.DISABLECRYPTO");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLERPRES)) == 1073741824ULL, "HostFeatures.ENABLERPRES");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLERPRES)) == 2147483648ULL, "HostFeatures.DISABLERPRES");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESVEBITPERM)) == 4294967296ULL, "HostFeatures.ENABLESVEBITPERM");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESVEBITPERM)) == 8589934592ULL, "HostFeatures.DISABLESVEBITPERM");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEPRESERVEALLABI)) == 17179869184ULL, "HostFeatures.ENABLEPRESERVEALLABI");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEPRESERVEALLABI)) == 34359738368ULL, "HostFeatures.DISABLEPRESERVEALLABI");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEWFXT)) == 68719476736ULL, "HostFeatures.ENABLEWFXT");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEWFXT)) == 137438953472ULL, "HostFeatures.DISABLEWFXT");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLE3DNOW)) == 274877906944ULL, "HostFeatures.ENABLE3DNOW");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLE3DNOW)) == 549755813888ULL, "HostFeatures.DISABLE3DNOW");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESSE4A)) == 1099511627776ULL, "HostFeatures.ENABLESSE4A");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESSE4A)) == 2199023255552ULL, "HostFeatures.DISABLESSE4A");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEMOPS)) == 4398046511104ULL, "HostFeatures.ENABLEMOPS");
static_assert((static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEMOPS)) == 8796093022208ULL, "HostFeatures.DISABLEMOPS");
static_assert((static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::OFF)) == 0ULL, "PassManagerDumpIR.OFF");
static_assert((static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::BEFOREOPT)) == 1ULL, "PassManagerDumpIR.BEFOREOPT");
static_assert((static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::AFTEROPT)) == 2ULL, "PassManagerDumpIR.AFTEROPT");
static_assert((static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::BEFOREPASS)) == 4ULL, "PassManagerDumpIR.BEFOREPASS");
static_assert((static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::AFTERPASS)) == 8ULL, "PassManagerDumpIR.AFTERPASS");
static_assert((static_cast<uint64_t>(FEXCore::Config::Disassemble::OFF)) == 0ULL, "Disassemble.OFF");
static_assert((static_cast<uint64_t>(FEXCore::Config::Disassemble::DISPATCHER)) == 1ULL, "Disassemble.DISPATCHER");
static_assert((static_cast<uint64_t>(FEXCore::Config::Disassemble::BLOCKS)) == 2ULL, "Disassemble.BLOCKS");
static_assert((static_cast<uint64_t>(FEXCore::Config::Disassemble::STATS)) == 4ULL, "Disassemble.STATS");
extern "C" {
__attribute__((used, visibility("default"), section("__DATA,__ideck_fex")))
extern const uint64_t ideck_fex_layout_v1[] = {
  1, // 0 schema
  sizeof(void*), // 1 pointer_size
  FEXCore::Utils::FEX_PAGE_SIZE, // 2 FEX_PAGE_SIZE
  sizeof(FEXCore::UncheckedLongJump::JumpBuf), // 3 JumpBuf.sizeof
  alignof(FEXCore::UncheckedLongJump::JumpBuf), // 4 JumpBuf.alignof
  sizeof(FEXCore::Core::InternalThreadState), // 5 InternalThreadState.sizeof
  alignof(FEXCore::Core::InternalThreadState), // 6 InternalThreadState.alignof
  sizeof(FEXCore::Core::CpuStateFrame), // 7 CpuStateFrame.sizeof
  alignof(FEXCore::Core::CpuStateFrame), // 8 CpuStateFrame.alignof
  sizeof(FEXCore::Core::CPUState), // 9 CPUState.sizeof
  alignof(FEXCore::Core::CPUState), // 10 CPUState.alignof
  sizeof(FEXCore::Core::JITPointers), // 11 JITPointers.sizeof
  alignof(FEXCore::Core::JITPointers), // 12 JITPointers.alignof
  sizeof(FEXCore::Core::CPUState::gdt_segment), // 13 gdt_segment.sizeof
  alignof(FEXCore::Core::CPUState::gdt_segment), // 14 gdt_segment.alignof
  sizeof(FEXCore::Core::UnalignedExclusiveStore), // 15 UnalignedExclusiveStore.sizeof
  alignof(FEXCore::Core::UnalignedExclusiveStore), // 16 UnalignedExclusiveStore.alignof
  offsetof(FEXCore::UncheckedLongJump::JumpBuf, Registers), // 17 JumpBuf.Registers.offsetof
  offsetof(FEXCore::Core::InternalThreadState, CurrentFrame), // 18 InternalThreadState.CurrentFrame.offsetof
  offsetof(FEXCore::Core::InternalThreadState, CTX), // 19 InternalThreadState.CTX.offsetof
  offsetof(FEXCore::Core::InternalThreadState, OpDispatcher), // 20 InternalThreadState.OpDispatcher.offsetof
  offsetof(FEXCore::Core::InternalThreadState, CPUBackend), // 21 InternalThreadState.CPUBackend.offsetof
  offsetof(FEXCore::Core::InternalThreadState, LookupCache), // 22 InternalThreadState.LookupCache.offsetof
  offsetof(FEXCore::Core::InternalThreadState, FrontendDecoder), // 23 InternalThreadState.FrontendDecoder.offsetof
  offsetof(FEXCore::Core::InternalThreadState, PassManager), // 24 InternalThreadState.PassManager.offsetof
  offsetof(FEXCore::Core::InternalThreadState, SymbolBuffer), // 25 InternalThreadState.SymbolBuffer.offsetof
  offsetof(FEXCore::Core::InternalThreadState, ThreadStats), // 26 InternalThreadState.ThreadStats.offsetof
  offsetof(FEXCore::Core::InternalThreadState, ExclusiveStore), // 27 InternalThreadState.ExclusiveStore.offsetof
  offsetof(FEXCore::Core::InternalThreadState, FrontendPtr), // 28 InternalThreadState.FrontendPtr.offsetof
  offsetof(FEXCore::Core::InternalThreadState, CallRetStackBase), // 29 InternalThreadState.CallRetStackBase.offsetof
  offsetof(FEXCore::Core::InternalThreadState, JITGuardPage), // 30 InternalThreadState.JITGuardPage.offsetof
  offsetof(FEXCore::Core::InternalThreadState, JITGuardOverflowArgument), // 31 InternalThreadState.JITGuardOverflowArgument.offsetof
  offsetof(FEXCore::Core::InternalThreadState, RestartJump), // 32 InternalThreadState.RestartJump.offsetof
  offsetof(FEXCore::Core::InternalThreadState, BaseFrameState), // 33 InternalThreadState.BaseFrameState.offsetof
  offsetof(FEXCore::Core::InternalThreadState, InterruptFaultPage), // 34 InternalThreadState.InterruptFaultPage.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, State), // 35 CpuStateFrame.State.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, ReturningStackLocation), // 36 CpuStateFrame.ReturningStackLocation.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, InSyscallInfo), // 37 CpuStateFrame.InSyscallInfo.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, SignalHandlerRefCounter), // 38 CpuStateFrame.SignalHandlerRefCounter.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, SynchronousFaultData), // 39 CpuStateFrame.SynchronousFaultData.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, Thread), // 40 CpuStateFrame.Thread.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, Pointers), // 41 CpuStateFrame.Pointers.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, IosLastEnterECRip), // 42 CpuStateFrame.IosLastEnterECRip.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, IosLastCallbackRip), // 43 CpuStateFrame.IosLastCallbackRip.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, IosLastCallbackLR), // 44 CpuStateFrame.IosLastCallbackLR.offsetof
  offsetof(FEXCore::Core::CpuStateFrame, IosGuestBranchHistory), // 45 CpuStateFrame.IosGuestBranchHistory.offsetof
  offsetof(FEXCore::Core::CPUState, InlineJITBlockHeader), // 46 CPUState.InlineJITBlockHeader.offsetof
  offsetof(FEXCore::Core::CPUState, DeferredSignalRefCount), // 47 CPUState.DeferredSignalRefCount.offsetof
  offsetof(FEXCore::Core::CPUState, pf_raw), // 48 CPUState.pf_raw.offsetof
  offsetof(FEXCore::Core::CPUState, af_raw), // 49 CPUState.af_raw.offsetof
  offsetof(FEXCore::Core::CPUState, rip), // 50 CPUState.rip.offsetof
  offsetof(FEXCore::Core::CPUState, gregs), // 51 CPUState.gregs.offsetof
  offsetof(FEXCore::Core::CPUState, L1Pointer), // 52 CPUState.L1Pointer.offsetof
  offsetof(FEXCore::Core::CPUState, L1Mask), // 53 CPUState.L1Mask.offsetof
  offsetof(FEXCore::Core::CPUState, callret_sp), // 54 CPUState.callret_sp.offsetof
  offsetof(FEXCore::Core::CPUState, callret_sp_base), // 55 CPUState.callret_sp_base.offsetof
  offsetof(FEXCore::Core::CPUState, avx_high), // 56 CPUState.avx_high.offsetof
  offsetof(FEXCore::Core::CPUState, xmm), // 57 CPUState.xmm.offsetof
  offsetof(FEXCore::Core::CPUState, es_idx), // 58 CPUState.es_idx.offsetof
  offsetof(FEXCore::Core::CPUState, cs_idx), // 59 CPUState.cs_idx.offsetof
  offsetof(FEXCore::Core::CPUState, ss_idx), // 60 CPUState.ss_idx.offsetof
  offsetof(FEXCore::Core::CPUState, ds_idx), // 61 CPUState.ds_idx.offsetof
  offsetof(FEXCore::Core::CPUState, gs_idx), // 62 CPUState.gs_idx.offsetof
  offsetof(FEXCore::Core::CPUState, fs_idx), // 63 CPUState.fs_idx.offsetof
  offsetof(FEXCore::Core::CPUState, mxcsr), // 64 CPUState.mxcsr.offsetof
  offsetof(FEXCore::Core::CPUState, es_cached), // 65 CPUState.es_cached.offsetof
  offsetof(FEXCore::Core::CPUState, cs_cached), // 66 CPUState.cs_cached.offsetof
  offsetof(FEXCore::Core::CPUState, ss_cached), // 67 CPUState.ss_cached.offsetof
  offsetof(FEXCore::Core::CPUState, ds_cached), // 68 CPUState.ds_cached.offsetof
  offsetof(FEXCore::Core::CPUState, gs_cached), // 69 CPUState.gs_cached.offsetof
  offsetof(FEXCore::Core::CPUState, fs_cached), // 70 CPUState.fs_cached.offsetof
  offsetof(FEXCore::Core::CPUState, flags), // 71 CPUState.flags.offsetof
  offsetof(FEXCore::Core::CPUState, mm), // 72 CPUState.mm.offsetof
  offsetof(FEXCore::Core::CPUState, segment_arrays), // 73 CPUState.segment_arrays.offsetof
  offsetof(FEXCore::Core::CPUState, FCW), // 74 CPUState.FCW.offsetof
  offsetof(FEXCore::Core::CPUState, AbridgedFTW), // 75 CPUState.AbridgedFTW.offsetof
  offsetof(FEXCore::Core::CPUState, private_gdt), // 76 CPUState.private_gdt.offsetof
  offsetof(FEXCore::Core::JITPointers, SyscallHandlerObj), // 77 JITPointers.SyscallHandlerObj.offsetof
  offsetof(FEXCore::Core::JITPointers, SyscallHandlerFunc), // 78 JITPointers.SyscallHandlerFunc.offsetof
  offsetof(FEXCore::Core::JITPointers, ThreadStopHandlerSpillSRA), // 79 JITPointers.ThreadStopHandlerSpillSRA.offsetof
  offsetof(FEXCore::Core::JITPointers, TelemetryValueAddresses), // 80 JITPointers.TelemetryValueAddresses.offsetof
  offsetof(FEXCore::Core::JITPointers, NamedVectorConstants), // 81 JITPointers.NamedVectorConstants.offsetof
  offsetof(FEXCore::Core::UnalignedExclusiveStore, Addr), // 82 UnalignedExclusiveStore.Addr.offsetof
  offsetof(FEXCore::Core::UnalignedExclusiveStore, Store), // 83 UnalignedExclusiveStore.Store.offsetof
  offsetof(FEXCore::Core::UnalignedExclusiveStore, Size), // 84 UnalignedExclusiveStore.Size.offsetof
  sizeof(FEXCore::UncheckedLongJump::JumpBuf::Registers) / sizeof(uint64_t), // 85 JumpBuf.register_count
  FEXCore::Core::InternalThreadState::CALLRET_STACK_SIZE, // 86 InternalThreadState.CALLRET_STACK_SIZE
  FEXCore::Core::InternalThreadState::CALLRET_DEFAULT_OFFSET, // 87 InternalThreadState.CALLRET_DEFAULT_OFFSET
  FEXCore::Core::InternalThreadState::CALLRET_LIVE_OFFSET, // 88 InternalThreadState.CALLRET_LIVE_OFFSET
  FEXCore::Core::InternalThreadState::CALLRET_LIVE_SIZE, // 89 InternalThreadState.CALLRET_LIVE_SIZE
  sizeof(FEXCore::Core::InternalThreadState::InterruptFaultPage), // 90 InternalThreadState.InterruptFaultPage.sizeof
  sizeof(FEXCore::Config::Layer), // 91 ConfigLayer.sizeof
  alignof(FEXCore::Config::Layer), // 92 ConfigLayer.alignof
  sizeof(FEXCore::Config::LayerValue), // 93 ConfigLayerValue.sizeof
  alignof(FEXCore::Config::LayerValue), // 94 ConfigLayerValue.alignof
  sizeof(FEXCore::Config::LayerOptions), // 95 ConfigLayerOptions.sizeof
  alignof(FEXCore::Config::LayerOptions), // 96 ConfigLayerOptions.alignof
  static_cast<uint64_t>(FEXCore::Config::CONFIG_MULTIBLOCK), // 97 CONFIG_MULTIBLOCK
  static_cast<uint64_t>(FEXCore::Config::CONFIG_MAXINST), // 98 CONFIG_MAXINST
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLECODECACHINGWIP), // 99 CONFIG_ENABLECODECACHINGWIP
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLELAZYCODECACHINGWIP), // 100 CONFIG_ENABLELAZYCODECACHINGWIP
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLECODECACHEVALIDATION), // 101 CONFIG_ENABLECODECACHEVALIDATION
  static_cast<uint64_t>(FEXCore::Config::CONFIG_HOSTFEATURES), // 102 CONFIG_HOSTFEATURES
  static_cast<uint64_t>(FEXCore::Config::CONFIG_SMALLTSCSCALE), // 103 CONFIG_SMALLTSCSCALE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_HIDEHYBRID), // 104 CONFIG_HIDEHYBRID
  static_cast<uint64_t>(FEXCore::Config::CONFIG_CPUFEATUREREGISTERS), // 105 CONFIG_CPUFEATUREREGISTERS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ROOTFS), // 106 CONFIG_ROOTFS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKHOSTLIBS), // 107 CONFIG_THUNKHOSTLIBS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKGUESTLIBS), // 108 CONFIG_THUNKGUESTLIBS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_THUNKCONFIG), // 109 CONFIG_THUNKCONFIG
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ENV), // 110 CONFIG_ENV
  static_cast<uint64_t>(FEXCore::Config::CONFIG_HOSTENV), // 111 CONFIG_HOSTENV
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ADDITIONALARGUMENTS), // 112 CONFIG_ADDITIONALARGUMENTS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLEL2CACHE), // 113 CONFIG_DISABLEL2CACHE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHE), // 114 CONFIG_DYNAMICL1CACHE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHEINCREASECOUNTHEURISTIC), // 115 CONFIG_DYNAMICL1CACHEINCREASECOUNTHEURISTIC
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DYNAMICL1CACHEDECREASECOUNTHEURISTIC), // 116 CONFIG_DYNAMICL1CACHEDECREASECOUNTHEURISTIC
  static_cast<uint64_t>(FEXCore::Config::CONFIG_SINGLESTEP), // 117 CONFIG_SINGLESTEP
  static_cast<uint64_t>(FEXCore::Config::CONFIG_GDBSERVER), // 118 CONFIG_GDBSERVER
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DUMPIR), // 119 CONFIG_DUMPIR
  static_cast<uint64_t>(FEXCore::Config::CONFIG_PASSMANAGERDUMPIR), // 120 CONFIG_PASSMANAGERDUMPIR
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DUMPGPRS), // 121 CONFIG_DUMPGPRS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_O0), // 122 CONFIG_O0
  static_cast<uint64_t>(FEXCore::Config::CONFIG_GLOBALJITNAMING), // 123 CONFIG_GLOBALJITNAMING
  static_cast<uint64_t>(FEXCore::Config::CONFIG_LIBRARYJITNAMING), // 124 CONFIG_LIBRARYJITNAMING
  static_cast<uint64_t>(FEXCore::Config::CONFIG_BLOCKJITNAMING), // 125 CONFIG_BLOCKJITNAMING
  static_cast<uint64_t>(FEXCore::Config::CONFIG_GDBSYMBOLS), // 126 CONFIG_GDBSYMBOLS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_INJECTLIBSEGFAULT), // 127 CONFIG_INJECTLIBSEGFAULT
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DISASSEMBLE), // 128 CONFIG_DISASSEMBLE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_X86DISASSEMBLE), // 129 CONFIG_X86DISASSEMBLE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_FORCESVEWIDTH), // 130 CONFIG_FORCESVEWIDTH
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLETELEMETRY), // 131 CONFIG_DISABLETELEMETRY
  static_cast<uint64_t>(FEXCore::Config::CONFIG_SILENTLOG), // 132 CONFIG_SILENTLOG
  static_cast<uint64_t>(FEXCore::Config::CONFIG_OUTPUTLOG), // 133 CONFIG_OUTPUTLOG
  static_cast<uint64_t>(FEXCore::Config::CONFIG_TELEMETRYDIRECTORY), // 134 CONFIG_TELEMETRYDIRECTORY
  static_cast<uint64_t>(FEXCore::Config::CONFIG_PROFILESTATS), // 135 CONFIG_PROFILESTATS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_ENABLEGPUVISPROFILING), // 136 CONFIG_ENABLEGPUVISPROFILING
  static_cast<uint64_t>(FEXCore::Config::CONFIG_SMCCHECKS), // 137 CONFIG_SMCCHECKS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_TSOENABLED), // 138 CONFIG_TSOENABLED
  static_cast<uint64_t>(FEXCore::Config::CONFIG_VECTORTSOENABLED), // 139 CONFIG_VECTORTSOENABLED
  static_cast<uint64_t>(FEXCore::Config::CONFIG_MEMCPYSETTSOENABLED), // 140 CONFIG_MEMCPYSETTSOENABLED
  static_cast<uint64_t>(FEXCore::Config::CONFIG_HALFBARRIERTSOENABLED), // 141 CONFIG_HALFBARRIERTSOENABLED
  static_cast<uint64_t>(FEXCore::Config::CONFIG_STRICTINPROCESSSPLITLOCKS), // 142 CONFIG_STRICTINPROCESSSPLITLOCKS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_KERNELUNALIGNEDATOMICBACKPATCHING), // 143 CONFIG_KERNELUNALIGNEDATOMICBACKPATCHING
  static_cast<uint64_t>(FEXCore::Config::CONFIG_VOLATILEMETADATA), // 144 CONFIG_VOLATILEMETADATA
  static_cast<uint64_t>(FEXCore::Config::CONFIG_X87REDUCEDPRECISION), // 145 CONFIG_X87REDUCEDPRECISION
  static_cast<uint64_t>(FEXCore::Config::CONFIG_STALLPROCESS), // 146 CONFIG_STALLPROCESS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_HIDEHYPERVISORBIT), // 147 CONFIG_HIDEHYPERVISORBIT
  static_cast<uint64_t>(FEXCore::Config::CONFIG_STARTUPSLEEP), // 148 CONFIG_STARTUPSLEEP
  static_cast<uint64_t>(FEXCore::Config::CONFIG_STARTUPSLEEPPROCNAME), // 149 CONFIG_STARTUPSLEEPPROCNAME
  static_cast<uint64_t>(FEXCore::Config::CONFIG_MONOHACKS), // 150 CONFIG_MONOHACKS
  static_cast<uint64_t>(FEXCore::Config::CONFIG_SERVERSOCKETPATH), // 151 CONFIG_SERVERSOCKETPATH
  static_cast<uint64_t>(FEXCore::Config::CONFIG_NEEDSSECCOMP), // 152 CONFIG_NEEDSSECCOMP
  static_cast<uint64_t>(FEXCore::Config::CONFIG_EXTENDEDVOLATILEMETADATA), // 153 CONFIG_EXTENDEDVOLATILEMETADATA
  static_cast<uint64_t>(FEXCore::Config::CONFIG_INTERPRETER_INSTALLED), // 154 CONFIG_INTERPRETER_INSTALLED
  static_cast<uint64_t>(FEXCore::Config::CONFIG_APP_FILENAME), // 155 CONFIG_APP_FILENAME
  static_cast<uint64_t>(FEXCore::Config::CONFIG_APP_CONFIG_NAME), // 156 CONFIG_APP_CONFIG_NAME
  static_cast<uint64_t>(FEXCore::Config::CONFIG_IS64BIT_MODE), // 157 CONFIG_IS64BIT_MODE
  static_cast<uint64_t>(FEXCore::Config::CONFIG_DISABLE_VIXL_INDIRECT_RUNTIME_CALLS), // 158 CONFIG_DISABLE_VIXL_INDIRECT_RUNTIME_CALLS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::OFF), // 159 HostFeatures.OFF
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESVE), // 160 HostFeatures.ENABLESVE
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESVE), // 161 HostFeatures.DISABLESVE
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEAVX), // 162 HostFeatures.ENABLEAVX
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEAVX), // 163 HostFeatures.DISABLEAVX
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEAFP), // 164 HostFeatures.ENABLEAFP
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEAFP), // 165 HostFeatures.DISABLEAFP
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLELRCPC), // 166 HostFeatures.ENABLELRCPC
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLELRCPC), // 167 HostFeatures.DISABLELRCPC
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLELRCPC2), // 168 HostFeatures.ENABLELRCPC2
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLELRCPC2), // 169 HostFeatures.DISABLELRCPC2
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECSSC), // 170 HostFeatures.ENABLECSSC
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECSSC), // 171 HostFeatures.DISABLECSSC
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEPMULL128), // 172 HostFeatures.ENABLEPMULL128
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEPMULL128), // 173 HostFeatures.DISABLEPMULL128
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLERNG), // 174 HostFeatures.ENABLERNG
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLERNG), // 175 HostFeatures.DISABLERNG
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECLZERO), // 176 HostFeatures.ENABLECLZERO
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECLZERO), // 177 HostFeatures.DISABLECLZERO
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEATOMICS), // 178 HostFeatures.ENABLEATOMICS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEATOMICS), // 179 HostFeatures.DISABLEATOMICS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFCMA), // 180 HostFeatures.ENABLEFCMA
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFCMA), // 181 HostFeatures.DISABLEFCMA
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFLAGM), // 182 HostFeatures.ENABLEFLAGM
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFLAGM), // 183 HostFeatures.DISABLEFLAGM
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFLAGM2), // 184 HostFeatures.ENABLEFLAGM2
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFLAGM2), // 185 HostFeatures.DISABLEFLAGM2
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEFRINTTS), // 186 HostFeatures.ENABLEFRINTTS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEFRINTTS), // 187 HostFeatures.DISABLEFRINTTS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLECRYPTO), // 188 HostFeatures.ENABLECRYPTO
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLECRYPTO), // 189 HostFeatures.DISABLECRYPTO
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLERPRES), // 190 HostFeatures.ENABLERPRES
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLERPRES), // 191 HostFeatures.DISABLERPRES
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESVEBITPERM), // 192 HostFeatures.ENABLESVEBITPERM
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESVEBITPERM), // 193 HostFeatures.DISABLESVEBITPERM
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEPRESERVEALLABI), // 194 HostFeatures.ENABLEPRESERVEALLABI
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEPRESERVEALLABI), // 195 HostFeatures.DISABLEPRESERVEALLABI
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEWFXT), // 196 HostFeatures.ENABLEWFXT
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEWFXT), // 197 HostFeatures.DISABLEWFXT
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLE3DNOW), // 198 HostFeatures.ENABLE3DNOW
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLE3DNOW), // 199 HostFeatures.DISABLE3DNOW
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLESSE4A), // 200 HostFeatures.ENABLESSE4A
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLESSE4A), // 201 HostFeatures.DISABLESSE4A
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::ENABLEMOPS), // 202 HostFeatures.ENABLEMOPS
  static_cast<uint64_t>(FEXCore::Config::HostFeatures::DISABLEMOPS), // 203 HostFeatures.DISABLEMOPS
  static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::OFF), // 204 PassManagerDumpIR.OFF
  static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::BEFOREOPT), // 205 PassManagerDumpIR.BEFOREOPT
  static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::AFTEROPT), // 206 PassManagerDumpIR.AFTEROPT
  static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::BEFOREPASS), // 207 PassManagerDumpIR.BEFOREPASS
  static_cast<uint64_t>(FEXCore::Config::PassManagerDumpIR::AFTERPASS), // 208 PassManagerDumpIR.AFTERPASS
  static_cast<uint64_t>(FEXCore::Config::Disassemble::OFF), // 209 Disassemble.OFF
  static_cast<uint64_t>(FEXCore::Config::Disassemble::DISPATCHER), // 210 Disassemble.DISPATCHER
  static_cast<uint64_t>(FEXCore::Config::Disassemble::BLOCKS), // 211 Disassemble.BLOCKS
  static_cast<uint64_t>(FEXCore::Config::Disassemble::STATS), // 212 Disassemble.STATS
};
}
extern "C" {
__attribute__((used, visibility("default"), section("__DATA,__ideck_gdt")))
extern const FEXCore::Core::CPUState::gdt_segment ideck_fex_gdt_v1 = {
  .Limit0 = 0x1234, .Base0 = 0x5678, .Base1 = 0x9A, .Type = 0xB,
  .S = 1, .DPL = 2, .P = 1, .Limit1 = 0xC, .AVL = 1, .L = 0,
  .D = 1, .G = 1, .Base2 = 0xEF,
};
}
