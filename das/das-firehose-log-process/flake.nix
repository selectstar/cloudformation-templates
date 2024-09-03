{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
          };
        };
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryEnv overrides;
        app = mkPoetryEnv {
          python = pkgs.python312;
          projectDir = ./.;
          extraPackages = (ps: with ps; [
            python-lsp-server
            pylint
            black
          ]);
          overrides = overrides.withDefaults (final: prev: {
          });
        };
      in {
        devShells.default = app.env.overrideAttrs (old: {
          buildInputs = with pkgs; [
            awscli2
            poetry
            jq
          ];
        });
      });
}
