; Uninstall behaviour for Zaram.
;
; The default NSIS uninstaller removes the program and leaves everything under
; %APPDATA%\Zaram untouched. That stays the default: the data there is the
; user's memory, their egress log, their invoices and their per-host privacy
; rules. Deleting it because someone uninstalled an application is not a
; decision this installer gets to make silently.
;
; But "remove it completely" has to be possible, and the honest version of it
; offers to hand the data back first. Rule 7 — the Spine is exportable in an
; open format, no lock-in — and uninstall is precisely the moment lock-in would
; bite. An uninstaller that can only keep or destroy makes leaving expensive,
; which is the thing the rule exists to prevent.
;
; So: keep (default), export then delete, or delete. Two standard dialogs
; rather than a custom page, because a custom page in an uninstaller is a
; maintenance burden and these two questions are the whole decision.
;
; The ${isUpdated} guard is the important one. electron-builder runs the
; uninstaller as part of installing a new version, and a prompt there would ask
; the user to decide about their data during what they believe is an update,
; with a wrong answer wiping the Spine mid-upgrade. During an update this macro
; does nothing at all.

!macro customUnInstall
  ${ifNot} ${isUpdated}
    ; Nothing to ask about if nothing was ever written. A dialog offering to
    ; delete data that does not exist teaches the user their answer does not
    ; matter.
    IfFileExists "$APPDATA\Zaram\*.*" 0 zaramUninstallDone

    ; MB_DEFBUTTON2 focuses "No". Someone pressing Enter through a dialog they
    ; did not read keeps their data — the only outcome that can still be
    ; corrected afterwards. /SD IDNO makes a silent uninstall keep it too.
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 \
      "Also delete everything Zaram remembers?$\r$\n$\r$\n\
This removes what Zaram learned from your documents, the record of everything \
that ever left your machine, the invoices and documents it generated, and your \
per-source privacy settings.$\r$\n$\r$\n\
Your own files are never touched — only Zaram's copy of what it learned.$\r$\n$\r$\n\
Choose No to keep it all in case you reinstall." \
      /SD IDNO IDYES zaramAskExport IDNO zaramKeepData

    zaramAskExport:
      ; Defaulting to Yes here, unlike the question above. Saving a copy is
      ; never the destructive answer, so the safe default and the convenient
      ; one point the same way.
      MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON1 \
        "Save a copy to your Desktop first?$\r$\n$\r$\n\
Zaram will write a single .zip containing everything it holds, in open \
formats you can read without Zaram installed. Restoring later is a matter of \
unzipping it back.$\r$\n$\r$\n\
This is recommended — deleting cannot be undone." \
        /SD IDYES IDYES zaramExport IDNO zaramConfirmDelete

    zaramExport:
      DetailPrint "Saving a copy of your Zaram data to the Desktop..."
      ; PowerShell's Compress-Archive rather than a bundled zip tool: it is
      ; present on every supported Windows, so the export path cannot break
      ; because a helper failed to install. $$ is a literal $ in NSIS, so the
      ; timestamp is expanded by PowerShell rather than here — which is what
      ; keeps a second uninstall from overwriting the first backup.
      nsExec::ExecToLog 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \
"Compress-Archive -Path $\"$APPDATA\Zaram\*$\" -DestinationPath $\"$DESKTOP\Zaram-data-$$(Get-Date -Format yyyyMMdd-HHmmss).zip$\""'
      Pop $0
      ${If} $0 == 0
        MessageBox MB_OK|MB_ICONINFORMATION \
          "Saved to your Desktop as a Zaram-data zip file.$\r$\n$\r$\n\
Zaram's data will now be removed from this machine."
        Goto zaramRemoveData
      ${Else}
        ; The copy failed, so nothing is deleted. Deleting after a backup that
        ; did not happen is the single worst outcome available here, and it is
        ; worth stopping the uninstall's data step entirely to avoid it.
        MessageBox MB_OK|MB_ICONSTOP \
          "The copy could not be saved, so nothing has been deleted.$\r$\n$\r$\n\
Zaram itself has been removed. Your data is still in:$\r$\n$APPDATA\Zaram$\r$\n$\r$\n\
You can copy that folder somewhere safe and delete it yourself."
        Goto zaramUninstallDone
      ${EndIf}

    zaramConfirmDelete:
      ; Declining the backup is the one path that destroys data with no copy
      ; anywhere, so it is the one path that asks twice. Industry-standard for
      ; an irreversible action, and this is the most irreversible thing the
      ; product can do.
      MessageBox MB_YESNO|MB_ICONSTOP|MB_DEFBUTTON2 \
        "Delete without saving a copy?$\r$\n$\r$\n\
Everything Zaram remembers will be gone permanently, with no backup." \
        /SD IDNO IDYES zaramRemoveData IDNO zaramKeepData

    zaramRemoveData:
      DetailPrint "Removing Zaram's data..."
      ; Everything Zaram writes lives under one directory, which is what makes
      ; complete removal answerable at all. Anything that ever writes outside
      ; it must be added here, or "delete everything" quietly becomes a lie.
      RMDir /r "$APPDATA\Zaram"
      Goto zaramUninstallDone

    zaramKeepData:
      DetailPrint "Keeping your Zaram data. Reinstalling will pick it up again."
      Goto zaramUninstallDone

    zaramUninstallDone:
  ${endIf}
!macroend
