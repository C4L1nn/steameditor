; SplitForge NSIS Installer Script
; Generates a professional Windows installer for SplitForge

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ─── Metadata ───
Name "SplitForge — Steam Showcase Studio"
OutFile "SplitForge_Setup_${VERSION}.exe"
InstallDir "$LOCALAPPDATA\SplitForge"
InstallDirRegKey HKCU "Software\SplitForge" "InstallDir"

RequestExecutionLevel user
Unicode true

; ─── Branding ───
!define MUI_ICON "branding\app_icon.ico"
!define MUI_UNICON "branding\app_icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "branding\welcome.bmp"
!define MUI_HEADERIMAGE "branding\header.bmp"
!define MUI_HEADERIMAGE_BITMAP_NOSTRETCH
!define MUI_HEADERIMAGE_UNBITMAP "branding\header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP_NOSTRETCH

; ─── Pages ───
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\SplitForge.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch SplitForge now"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ─── Languages ───
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Turkish"

; ─── Reserved Files ───
ReserveFile "SplitForge.exe"
ReserveFile "resources\border_templates\*.png"
ReserveFile "GIF\bin\*.exe"

; ─── Installer Sections ───
Section "Main" SEC_MAIN
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "SplitForge.exe"
    File /r "resources"
    File /r "GIF"
    WriteRegStr HKCU "Software\SplitForge" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayName" "SplitForge"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "Publisher" "Aykut"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "URLInfoAbout" "https://github.com/aykut/steameditor"
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Start Menu Shortcut" SEC_SHORTCUT
    CreateDirectory "$SMPROGRAMS\SplitForge"
    CreateShortCut "$SMPROGRAMS\SplitForge\SplitForge.lnk" "$INSTDIR\SplitForge.exe"
    CreateShortCut "$SMPROGRAMS\SplitForge\Uninstall.lnk" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayIcon" "$INSTDIR\SplitForge.exe"
SectionEnd

Section "Desktop Shortcut" SEC_DESKTOP
    CreateShortCut "$DESKTOP\SplitForge.lnk" "$INSTDIR\SplitForge.exe"
SectionEnd

; ─── Uninstaller ───
Section "Uninstall"
    Delete "$INSTDIR\SplitForge.exe"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r "$INSTDIR\resources"
    RMDir /r "$INSTDIR\GIF"
    Delete "$SMPROGRAMS\SplitForge\*.*"
    RMDir "$SMPROGRAMS\SplitForge"
    Delete "$DESKTOP\SplitForge.lnk"
    DeleteRegKey HKCU "Software\SplitForge"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge"
SectionEnd

; ─── Functions ───
Function .onInit
    ; Check for running instance
    FindWindow $0 "SplitForge"
    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONEXCLAMATION "SplitForge is currently running. Please close it before installing." IDOK
        Abort
    ${EndIf}

    ; Check for admin (not required but warn)
    UserInfo::GetAccountType
    Pop $0
    ${If} $0 == "Admin"
        MessageBox MB_OK|MB_ICONINFORMATION "Installing as Administrator. This will install for all users." IDOK
    ${EndIf}
FunctionEnd

Function .onInstSuccess
    ; Create uninstall registry entries
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayName" "SplitForge"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "Publisher" "Aykut"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "URLInfoAbout" "https://github.com/aykut/steameditor"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SplitForge" "DisplayIcon" "$INSTDIR\SplitForge.exe"
FunctionEnd

; ─── Custom Pages (Optional) ───
; Function customPage
;     nsDialogs::Create 1018
;     Pop $0
;     ${If} $0 == error
;         Abort
;     ${EndIf}
;     ${NSD_CreateLabel} 0 0 100% 12u "Ready to install SplitForge ${VERSION}"
;     Pop $0
;     nsDialogs::Show
; FunctionEnd

; ─── Custom Uninstall Pages ───
Function un.onInit
    MessageBox MB_OKCANCEL|MB_ICONQUESTION "Are you sure you want to uninstall SplitForge?" IDOK +2
    Abort
FunctionEnd

Function un.onUninstSuccess
    ; Clean up start menu folder
    RMDir /r "$SMPROGRAMS\SplitForge"
    ; Remove desktop shortcut
    Delete "$DESKTOP\SplitForge.lnk"
    ; Show feedback
    MessageBox MB_OK "SplitForge has been uninstalled. Thank you for using it!"
FunctionEnd