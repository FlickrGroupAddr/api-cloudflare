export const CLEAN_CLIPBOARD_TEXT="FGA Plugin Code transfer finished.";
const CODE=/^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){11}-[0-9A-HJKMNP-TV-Z]{3}[0G]$/;
export function transferView({render,writeClipboard,schedule=setTimeout,cancel=clearTimeout}){
 let value="",copied=false,timer=null;
 const erase=()=>{value="";copied=false;if(timer!==null)cancel(timer);timer=null;render("",false);};
 return {
  get active(){return value!=="";},
  show(code){erase();if(typeof code!=="string"||!CODE.test(code))throw Error("invalid_transfer_response");value=code;render(value,true);timer=schedule(erase,300000);},
  async copy(){if(!value||copied)return false;copied=true;render(value,false);try{await writeClipboard(value);return true;}catch{return false;}},
  erase,
  async finish(){erase();try{await writeClipboard(CLEAN_CLIPBOARD_TEXT);return true;}catch{return false;}},
 };
}
