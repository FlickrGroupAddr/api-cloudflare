// Synthetic signing material only; consumed through the nonlogging subprocess wrapper.
import {generateKeyPair,exportJWK,importJWK,SignJWT} from "jose";
const chunks=[];for await(const part of process.stdin)chunks.push(part);const input=JSON.parse(Buffer.concat(chunks).toString("utf8"));
if(input.action==="generate"){const pair=await generateKeyPair("RS256",{extractable:true});process.stdout.write(JSON.stringify({publicKey:{...await exportJWK(pair.publicKey),kid:"proof-key",alg:"RS256",use:"sig"},privateKey:await exportJWK(pair.privateKey)}));}
else{const key=await importJWK(input.privateKey,"RS256"),now=Math.floor(Date.now()/1000);process.stdout.write(await new SignJWT({iss:"https://accounts.google.com",aud:"synthetic-client",sub:"synthetic-sub",nonce:input.nonce,iat:now,exp:now+3600}).setProtectedHeader({alg:"RS256",kid:"proof-key"}).sign(key));}
