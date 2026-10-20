package blue.core;

import blue.contracts.*;
import blue.coordination.*;
import blue.language.next.*;
import java.nio.file.*;
import java.util.*;

/** Consumes Python provider output using the actual MyOS protocol and Contracts engines. */
public final class ProviderCompatibility {
  @SuppressWarnings("unchecked") static Map<String,Object> obj(Object x) {return (Map<String,Object>)x;}
  @SuppressWarnings("unchecked") static List<Object> list(Object x) {return (List<Object>)x;}
  static Map<String,Object> map(Object... pairs) {
    var result=new LinkedHashMap<String,Object>();
    for(int i=0;i<pairs.length;i+=2)result.put(pairs[i].toString(),pairs[i+1]);return result;
  }
  static void check(boolean ok,String message) {if(!ok)throw new AssertionError(message);}
  public static void main(String[] args)throws Exception {
    var fixture=obj(ProviderProtocol.compactExact(WireData.json(Files.readString(Path.of(args[0])))));
    Path myos=Path.of(args[1]);
    var packages=new CompositionPackages(myos,Path.of(args[2]));
    var selection=obj(obj(CompositionPackages.yaml(myos.resolve("examples/independent-processes/packages.json"))).get("mounts"));
    for(String name:List.of("Language","BEX","Contracts","Coordination","Activation","Parties","Clauses","Connections","Amendments","Dispatch",
        "Agreements","Features","Commerce")) {
      var pin=obj(selection.get(name));
      packages.packages.put(name,BluePackage.open(myos.resolve(pin.get("path").toString()),pin.get("blueId").toString()));
    }
    try(var exact=new ProviderProtocol();var runtime=new AuthoringRuntime(RuntimeBindings.accessEvents())) {
      exact.remember(obj(fixture.get("objects")));
      var reader=new ProviderReader(exact,fixture.get("provider"));
      reader.attestation(fixture.get("descriptor"));
      var forged=new LinkedHashMap<String,Object>(obj(fixture.get("descriptor")));
      forged.put("signature","00".repeat(64));
      boolean rejected=false;
      try {reader.attestation(forged);}catch(IllegalArgumentException expected){rejected=true;}
      check(rejected,"Forged provider signature accepted");
      Object initial=fixture.get("initial");
      check(ProviderProtocol.accessBindings(initial).equals(RuntimeBindings.accessEvents()),"Wrong access edition");
      var state=SignedAccessReplay.execute(exact,initial,null,null,null,List.of(),fixture.get("provider"));
      var processor=runtime.processor(packages.language());
      processor.execution().values().nativeRuntime().mergeEvidence(exact.referencedEvidence(initial,fixture.get("phases")));
      processor.execution().values().refresh();
      int processed=1; // The first entry publishes the original document.
      for(Object raw:list(fixture.get("phases"))) {
        var phase=obj(raw);var response=phase.get("response");exact.stage(response);
        var page=reader.page(phase.get("query"),response);
        check(page.nextCursor()==null,"Incomplete fixture history");
        reader.accessPublication(phase.get("accessResponse"),fixture.get("accessId").toString());
        var payload=reader.attestation(response);var entries=list(obj(payload.get("page")).get("entries"));
        for(Object entry:entries.subList(processed,entries.size())) {
          state=SignedAccessReplay.execute(exact,initial,state.get("snapshot"),entry,
              payload.get("checkpoint"),entries,fixture.get("provider"));
        }
        processed=entries.size();
        String nativeId=exact.identify(state.get("current"));
        if(!nativeId.equals(phase.get("currentId"))) {
          System.out.println("PYTHON current: "+WireData.write(phase.get("current")));
          System.out.println("JAVA current: "+WireData.write(obj(obj(state.get("snapshot")).get("content")).get(nativeId)));
          throw new AssertionError("Python/Java state mismatch at "+phase.get("name"));
        }
        Object current=phase.get("current");
        var validate=map("contracts",map(
            "start",map("type","Contracts/Lifecycle Event Channel","event",map("type","Contracts/Document Processing Initiated")),
            "validate",map("type","Contracts/Sequential Workflow","channel","start","steps",List.of(
                map("type","Contracts/Compute","definition",map("type","Activation/Activation Functions"),
                    "do",List.of(map("$call",map("function","validateAccessDocument","args",map("access",current)))))))));
        Contracts.Result checked;
        try {checked=processor.initialize(validate);}
        catch(ContractException e) {throw new IllegalStateException(e.code()+" "+WireData.write(e.context()),e);}
        if(!checked.commits())ClauseGasProbe.diagnose(processor,validate);
        check(checked.commits(),"Activation rejected "+phase.get("name"));
        System.out.println("PASS "+phase.get("name")+": signed response, public history, identical Java replay, Activation validation");
      }
    }
  }
}
