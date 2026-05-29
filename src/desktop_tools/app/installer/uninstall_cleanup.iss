; Included from setup.iss — removes downloaded models, settings, and legacy caches.

[Code]
procedure UninstallCleanupUserData();
var
  Index: Integer;
  Path: string;
  Paths: TArrayOfString;
begin
  SetArrayLength(Paths, 4);
  Paths[0] := ExpandConstant('{localappdata}\Media Downloader');
  Paths[1] := ExpandConstant('{userprofile}\.u2net');
  Paths[2] := ExpandConstant('{userprofile}\.yamos_witch_mate');
  Paths[3] := ExpandConstant('{tmp}\media_downloader_bg_remover_diagnostics.txt');

  for Index := 0 to GetArrayLength(Paths) - 1 do
  begin
    Path := Paths[Index];
    if FileExists(Path) then
    begin
      DeleteFile(Path);
      Continue;
    end;
    if DirExists(Path) then
      DelTree(Path, True, True, True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    UninstallCleanupUserData();
end;
