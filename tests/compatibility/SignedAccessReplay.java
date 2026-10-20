package blue.coordination;

import static blue.coordination.ProviderProtocol.*;
import static blue.coordination.ProviderReader.require;
import blue.contracts.*;
import blue.language.next.*;
import java.util.*;

/** Local signed-history adapter for the real MyOS Contracts engine.
 * Based on MyOS ProviderAccessExecution (65cd6d0). This fixture owns transport
 * admission only; package programs, state transitions and identities are native.
 * Compare receipt generations numerically: JSON receipt decoding can use a
 * different Number subclass than ExternalContext.generation() (a Java long).
 */
public final class SignedAccessReplay {
  public static String operationRequestType() {
    return operationRequestType(RuntimeBindings.current());
  }
  public static String operationRequestType(RuntimeBindings bindings) {
    try(var blue=Blue.builder().build()) { return new Contracts(blue,bindings).types().get("Operation Request"); }
  }
  private SignedAccessReplay() {}
  @SuppressWarnings("unchecked")
  public static Map<String,Object> execute(ProviderProtocol exact,Object initial,Object snapshot,Object event,Object checkpoint,List<Object> entries,Object provider) {
    var reader=new ProviderReader(exact,provider);var access=reader.kind(initial,"Timeline Access");
    var bindings=accessBindings(access);var types=types(bindings);
    var contracts=(Map<String,Object>)access.get("contracts");var channel=reader.kind(contracts.get("provider"),"Public Timeline Channel");
    require(contracts.keySet().equals(Set.of("provider","update")),"EXTRA_ACCESS_CONTRACT");
    require(exact.identify(contracts.get("update")).equals(exact.identify(typed(bindings,"Update Timeline Access"))),"CHANGED_ACCESS_PROGRAM");
    require(exact.identify(channel.get("provider")).equals(reader.providerId),"WRONG_PROVIDER");
    String channelId=exact.identify(channel),control=exact.identify(typed("Signed Timeline","provider",channel.get("provider"),"url",channel.get("url"),"publicRead",true));
    try(var blue=Blue.builder().packages(PackageBundle.builder().mount("Coordination",publication(bindings)).build()).build()) {
      var p=new Contracts(blue,bindings);
      p.execution().values().nativeRuntime().addPublicEvidence(records(bindings));
      p.execution().values().nativeRuntime().addEvidence(exact.referencedEvidence(initial,entries));p.execution().values().refresh();
      p.installInterpretedType(types.get("Update Timeline Access"),rules(bindings));
      String binding=types.get("Public Timeline Channel");
      p.installAdditiveRuntime(new ContractRuntime.Binding(binding,ProviderProtocol.RULES,"external-channel",List.of("provider","url"),List.of(),"coordinationPublicTimeline",Map.of("accept",1L),true,List.of(),"live"),new ContractRuntime.Implementation(){
        public boolean verifiesAdmission(){return true;}
        public Map<String,Object> verifyAdmission(ContractRuntime.AdmissionContext context){
          require(context.evidence()!=null,"MISSING_PUBLIC_HISTORY");var g=reader.checkpoint(checkpoint);
          require(control.equals(reader.timeline(g.get("timeline"))),"WRONG_CONTROL_TIMELINE");
          long last=-1;String prev=null;boolean found=false;
          for(Object raw:entries){var e=reader.kind(raw,"Timeline Entry");String id=exact.identify(e);
            require(control.equals(reader.timeline(e.get("timeline")))&&Objects.equals(prev,e.containsKey("prevEntry")?exact.identify(e.get("prevEntry")):null),"CHAIN_GAP");
            long ts=ProviderReader.number(e.get("timestamp"),0,9007199254740990L);require(ts>last,"INVALID_TIMELINE_ORDER");last=ts;prev=id;
            if(id.equals(context.event())){require(ts==context.timestamp(),"WRONG_EVENT_TIME");found=true;}
          }
          require(found&&last<ProviderReader.number(g.get("completeBefore"),0,9007199254740991L)&&Objects.equals(prev,g.containsKey("lastEntry")?exact.identify(g.get("lastEntry")):null),"INCOMPLETE_PUBLIC_HISTORY");
          var recipients=new ArrayList<Object>();
          for(Object raw:context.members()){var row=(Map<String,Object>)raw;if(channelId.equals(row.get("declaration")))recipients.add(List.of(row.get("member"),row.get("document"),row.get("channel"),row.get("generation")));}
          require(!recipients.isEmpty(),"WRONG_CHANNEL_DECLARATION");return Map.of("recipients",recipients);
        }
        public boolean accept(ContractRuntime.ExternalContext c){c.gas().charge("accept");var proof=(Map<String,Object>)c.evidence();return ((List<?>)proof.get("recipients")).stream().anyMatch(raw -> {
          var row=(List<?>)raw;
          return row.get(0).equals(c.member()) && row.get(1).equals(c.document())
              && row.get(2).equals(c.channel()) && ((Number)row.get(3)).longValue()==c.generation();
        });}
      });
      Contracts.Document state=snapshot==null?p.create(initial):p.importSnapshot((Map<String,Object>)snapshot,(String)((Map<String,Object>)snapshot).get("identity"));
      // The previous-entry links are part of the signed proof and must resolve in the
      // invocation's native evidence scope, including after a cold snapshot restore.
      p.execution().values().source(initial);
      for(Object entry:entries)p.execution().values().source(entry);
      if(event!=null){var e=reader.kind(event,"Timeline Entry");var result=p.process(state,event,ProviderReader.number(e.get("timestamp"),0,9007199254740990L),Map.of(binding,Map.of("verified",true)));
        require(result.commits(),"ACCESS_EXECUTION_FAILED: "+WireData.write(result.observations()));state=result.document();}
      return Map.of("current",WireData.json(p.toJson(state)),"snapshot",p.exportSnapshot(state));
    }
  }
}
