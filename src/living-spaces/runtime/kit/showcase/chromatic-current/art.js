// Original procedural artwork. No observations, imported images or simulated data.
export const palettes={
 tidal:{name:'Tidal',ground:'#173dbe',warp:['#6789ee','#a0bafa','#436ae1'],weft:['#fa8054','#ffc09a','#ef643d'],highlight:'#e1baf4',description:'cobalt, orange and lilac'},
 citrus:{name:'Citrus',ground:'#075951',warp:['#33897c','#75bba9','#206f62'],weft:['#cfdf65','#f1eda6','#aabb3b'],highlight:'#9ddbe6',description:'deep teal, citron and pale aqua'},
 ember:{name:'Ember',ground:'#661f40',warp:['#a75979','#d58ca4','#883553'],weft:['#ecaa7b','#f9d6a5','#d17a5c'],highlight:'#efb7d5',description:'mulberry, apricot and rose'}
};
export function draw(canvas,{seed,palette,phase}){
 const c=canvas.getContext('2d');if(!c)return false;
 const w=canvas.width,h=canvas.height,p=palettes[palette],s=seed*.173;
 c.fillStyle=p.ground;c.fillRect(0,0,w,h);
 // The warp bends as one cloth; the weft crosses in a different frequency.
 const warp=(x,y)=>x+Math.sin(y/h*5.1+s+phase*.23)*w*.075+Math.sin(y/h*2.3-s)*w*.06;
 c.lineWidth=Math.max(1,w*.0011);
 for(let i=-25;i<150;i++){
  const x=i*w/120;c.beginPath();
  for(let j=0;j<=64;j++){const y=j*h/64,xx=warp(x,y);j?c.lineTo(xx,y):c.moveTo(xx,y);}
  c.strokeStyle=p.warp[((i%3)+3)%3];c.stroke();
 }
 // Seven wide woven ribbons, made of fine parallel threads, never a stock chart.
 for(let band=-1;band<7;band++){
  for(let thread=0;thread<23;thread++){
   c.beginPath();
   for(let j=0;j<=96;j++){
    const x=j*w/96,t=x/w;
    const y=(band/5.8)*h+Math.sin(t*5.8+s+phase*.18+band*.32)*h*.15+Math.sin(t*2.5-s)*h*.10+thread*h*.0030;
    j?c.lineTo(x,y):c.moveTo(x,y);
   }
   c.strokeStyle=thread<3?p.highlight:p.weft[thread<9?1:thread<18?0:2];
   c.lineWidth=Math.max(1.4,h*.0024);c.stroke();
  }
 }
 // Highlight warp threads cross over the ribbons at alternating intervals.
 c.lineWidth=Math.max(.7,w*.0009);
 for(let i=0;i<120;i+=3){
  c.beginPath();let pen=false;
  for(let j=0;j<=160;j++){
   const y=j*h/160,x=warp(i*w/120,y),gate=Math.sin(y/h*19+x/w*6+s);
   if(gate>.6){pen?c.lineTo(x,y):c.moveTo(x,y);pen=true;}else pen=false;
  }
  c.strokeStyle=p.warp[1];c.stroke();
 }
 return true;
}
