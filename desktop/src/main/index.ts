import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import { AppLifecycle } from './lifecycle'

const lifecycle = new AppLifecycle()

app.whenReady().then(async () => {
  await lifecycle.initialize()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await lifecycle.initialize()
  }
})

app.on('before-quit', async () => {
  await lifecycle.shutdown()
})

ipcMain.handle('dialog:open-file', async (event, options) => {
  const { dialog } = require('electron')
  const result = await dialog.showOpenDialog(options)
  return result
})

ipcMain.handle('dialog:save-file', async (event, options) => {
  const { dialog } = require('electron')
  const result = await dialog.showSaveDialog(options)
  return result
})

ipcMain.handle('dialog:select-directory', async (event, options) => {
  const { dialog } = require('electron')
  const result = await dialog.showOpenDialog({
    ...options,
    properties: ['openDirectory']
  })
  return result
})
