// Start a same-site navigation without reading or transporting the session cookie.
const target=document.querySelector("[data-auth-continue]")?.getAttribute("href");
const allowed=new Set(["/admin/","/admin/?flickr=linked","/admin/?flickr=unconfirmed"]);
window.location.replace(allowed.has(target)?target:"/admin/");
