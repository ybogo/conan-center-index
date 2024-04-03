import os

from conan import ConanFile
from conans.errors import ConanInvalidConfiguration, ConanException
from conan.tools.files import copy, apply_conandata_patches, export_conandata_patches
from conan.tools.scm.git import Git
from conan.tools.layout import basic_layout

required_conan_version = ">=1.57.0"


class AerospikeConan(ConanFile):
    name = "aerospike-client-c"
    homepage = "https://github.com/aerospike/aerospike-client-c"
    description = "The Aerospike C client provides a C interface for interacting with the Aerospike Database."
    topics = ("aerospike", "client", "database")
    url = "https://github.com/conan-io/conan-center-index"
    license = "Apache-2.0"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "event_library": ["libev", "libuv", "libevent", None]
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "event_library": None,
    }

    def validate(self):
        if self.settings.os == "Windows":
            raise ConanInvalidConfiguration(
                "This recipe is not compatible with Windows")

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def requirements(self):
        self.requires("openssl/[>=1.1 <4]")
        self.requires("zlib/[>=1.2.11 <2]")

        # in the original code lua is used as a submodule.
        # when creating a new version, you need to manually check which version of lua is used in the submodule.
        if self.version == "6.6.0":
            self.requires(f"lua/5.4.6")

        if self.options.event_library == "libev":
            self.requires("libev/[>=4.24 <5]")
        elif self.options.event_library == "libuv":
            self.requires("libuv/[>=1.15.0 <2]")
        elif self.options.event_library == "libevent":
            self.requires("libevent/[>=2.1.8 <3]")

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        basic_layout(self, src_folder='src')

    def source(self):
        git = Git(self)
        clone_args = ['--depth', '1', '--branch',
                      self.version, '--single-branch', '.']
        git.clone(self.conan_data["sources"]
                  [self.version]['url'], args=clone_args)
        if git.get_commit() != self.conan_data["sources"][self.version]['sha256']:
            raise ConanException("tag {} commit sha256 {} do not match with provided in conandata.yml: {}".format(
                self.version, git.get_commit(), self.conan_data["sources"][self.version]['sha256']))
        self.run('git submodule update --init --recursive')

    def build(self):
        apply_conandata_patches(self)
        includes = []
        includes.append(self.deps_cpp_info['openssl'].rootpath)
        lua_include = f"{self.deps_cpp_info['lua'].rootpath}/include"
        event_library = ""
        if self.options.event_library:
            event_library = f"EVENT_LIB={self.options.event_library}"
            includes.append(self.deps_cpp_info[str(
                self.options.event_library)].rootpath)
        include_flags = ' '.join([f'-I{i}/include' for i in includes])

        self.run(
            f"make TARGET_BASE='target' {event_library} LUAMOD='{lua_include}' EXT_CFLAGS='{include_flags}' -C {self.source_path}")

    def package(self):
        lib_ext = 'so' if self.options.shared else 'a'
        copy(self, pattern=f"lib/*.{lib_ext}",
             src=f'{self.source_folder}/target', dst=self.package_folder)
        copy(self, pattern="*",
             src=f'{self.source_folder}/src/include', dst=f'{self.package_folder}/include')
        copy(self, pattern="*",
             src=f'{self.source_folder}/modules/common/src/include', dst=f'{self.package_folder}/include')
        copy(self, pattern="LICENSE.md", src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = ["aerospike"]

        self.cpp_info.defines = []
        if self.options.event_library == "libev":
            self.cpp_info.defines.append("AS_USE_LIBEV")
        elif self.options.event_library == "libuv":
            self.cpp_info.defines.append("AS_USE_LIBUV")
        elif self.options.event_library == "libevent":
            self.cpp_info.defines.append("AS_USE_LIBEVENT")
