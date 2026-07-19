"use client";
import { useEffect, useState } from "react";
import { API_URL, getToken } from "@/lib/api";

export function SecureMedia({ path, kind = "video" }: { path: string; kind?: "video" | "image" }) {
  const [url,setUrl]=useState<string>();
  useEffect(()=>{let objectUrl:string|undefined; fetch(`${API_URL}${path}`,{headers:{Authorization:`Bearer ${getToken()??""}`}}).then(r=>{if(!r.ok)throw new Error();return r.blob()}).then(blob=>{objectUrl=URL.createObjectURL(blob);setUrl(objectUrl)}).catch(()=>setUrl(undefined)); return()=>{if(objectUrl)URL.revokeObjectURL(objectUrl)}},[path]);
  if(!url) return <div className="empty">Protected evidence is loading or unavailable.</div>;
  return kind==="image"?<img src={url} alt="Redacted event evidence" style={{width:"100%",borderRadius:10}}/>:<video src={url} controls preload="metadata"/>;
}
