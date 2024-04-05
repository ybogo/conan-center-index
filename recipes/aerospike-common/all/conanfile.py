import os

from conan import ConanFile
from conan.tools.files import (
    copy,
    apply_conandata_patches,
    export_conandata_patches,
    get,
    download,
)
from conan.tools.layout import basic_layout

required_conan_version = ">=1.57.0"


class AerospikeCommonConan(ConanFile):
    name = "aerospike-common"
    homepage = "https://github.com/aerospike/aerospike-common"
    description = "Library for commonly used or shared code. Used by Aerospike Server and Aerospike C Client."
    url = "https://github.com/conan-io/conan-center-index"
    topics = ("aerospike", "client", "database")
    license = "Apache-2.0"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

    def requirements(self):
        self.requires("openssl/[>=1.1 <4]")
        self.requires("zlib/[>=1.2.11 <2]")

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        basic_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def build(self):
        apply_conandata_patches(self)
        includes = []
        for _, dependency in self.dependencies.items():
            for path in dependency.cpp_info.includedirs:
                includes.append(path)
        include_flags = " ".join([f"-I{i}" for i in includes])

        ld_flags = ""
        if self.options.shared:
            ld_flags = f"LDFLAGS='{self._get_ld_flags()}'"

        self.run(
            f"make TARGET_BASE='target' {ld_flags} EXT_CFLAGS='{include_flags}' -C {self.source_path}"
        )

    def package(self):
        if self.options.shared:
            copy(
                self,
                src=f"{self.source_folder}/target",
                pattern="lib/*.so*",
                dst=self.package_folder,
            )
            copy(
                self,
                src=f"{self.source_folder}/target",
                pattern="lib/*.dylib",
                dst=self.package_folder,
            )
        else:
            copy(
                self,
                src=f"{self.source_folder}/target",
                pattern="lib/*.a",
                dst=self.package_folder,
            )

        copy(
            self,
            pattern="*",
            src=f"{self.source_folder}/src/include",
            dst=f"{self.package_folder}/include",
        )
        download(
            self,
            "https://www.apache.org/licenses/LICENSE-2.0.txt",
            f"{self.package_folder}/licenses/LICENSE.txt",
        )

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = ["aerospike-common"]

    def _get_ld_flags(self):
        static_libs = []
        dynamic_libs_dirs = []
        dynamic_libs = []
        for _, dependency in self.dependencies.items():
            for dir in dependency.cpp_info.libdirs:
                # add path to search for dynamic libs
                dynamic_libs_dirs.append(f"-L{dir}")
                files = filter(
                    lambda item: os.path.isfile(os.path.join(dir, item)),
                    os.listdir(dir),
                )
                for lib in files:
                    if lib.endswith(".a"):
                        # add static lib only in case of shared build
                        static_libs.append(os.path.join(dir, lib))
                    else:
                        # add dynamic lib
                        dynamic_libs.append(f"-l{self._get_dynamic_library_name(lib)}")
        static_libs_str = " ".join(static_libs)
        dynamic_libs_dirs_str = " ".join(dynamic_libs_dirs)
        dynamic_libs_str = " ".join(dynamic_libs)
        return f"{dynamic_libs_dirs_str} {dynamic_libs_str} {static_libs_str}"

    def _get_dynamic_library_name(self, file_name):
        lib = file_name[3:]  # removes 'lib' prefix
        lib = lib.split(".", 1)[0]
        return lib
