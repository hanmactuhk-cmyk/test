const {app,BrowserWindow,ipcMain,dialog}=require('electron');
const path=require('path');
const fs=require('fs');
const {FlowEngine}=require('./automation/flow-engine');
const {ProfileManager}=require('./automation/profile-manager');
let win, engine;
const dataDir=path.join(app.getPath('userData'),'data'); fs.mkdirSync(dataDir,{recursive:true});
const pm=new ProfileManager(path.join(dataDir,'profiles.json'));
function createWindow(){win=new BrowserWindow({width:1450,height:920,minWidth:1100,minHeight:700,webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,nodeIntegration:false}});win.loadFile(path.join(__dirname,'renderer/index.html'));}
function emit(event,payload){if(win&&!win.isDestroyed())win.webContents.send(event,payload)}
app.whenReady().then(()=>{createWindow(); engine=new FlowEngine(pm,(e,p)=>emit(e,p));});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit()});
ipcMain.handle('profiles:list',()=>pm.list());
ipcMain.handle('profiles:add',async()=>{const p=await pm.addInteractive(); return p});
ipcMain.handle('profiles:remove',(_,id)=>pm.remove(id));
ipcMain.handle('profiles:refresh',(_,id)=>engine.refreshProfile(id));
ipcMain.handle('queue:run',(_,opts)=>engine.run(opts));
ipcMain.handle('queue:stop',()=>engine.stop());
ipcMain.handle('queue:pause',()=>engine.pause());
ipcMain.handle('queue:resume',()=>engine.resume());
ipcMain.handle('queue:import',async()=>{const r=await dialog.showOpenDialog(win,{properties:['openFile'],filters:[{name:'Prompt files',extensions:['txt','csv','json','xlsx','xls']}]}); if(r.canceled)return []; return engine.loadPrompts(r.filePaths[0]);});
ipcMain.handle('output:open',(_,file)=>require('electron').shell.openPath(file));
