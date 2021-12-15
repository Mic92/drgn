with import <nixpkgs> {};
python3.pkgs.buildPythonApplication {
  name = "drgn";
  src = ./.;
  postPatch = ''
    rm -rf .git
  '';
  buildInputs = [ elfutils ];
  nativeBuildInputs = [ autoconf automake libtool pkg-config ];
}
