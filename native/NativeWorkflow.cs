// Original MIT-licensed code; see ../LICENSE. Functional only: no clocks.
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace P054Native {
public static partial class Bridge {
    // Every arm independently acquires/decodes the same serialized document,
    // produces a full optimum certificate, serializes it, and consumes that
    // certificate through ParsePlan (which performs strict Check). Nothing from
    // another arm's plan, decoded Trace, mask, indices or arena is reused.
    static object ReplayExactDocument(byte[] input, string id, string planner) {
        Trace x;
        using(var stream=new MemoryStream(input,false))
        using(var doc=JsonDocument.Parse(stream)) x=ParseTrace(doc.RootElement,id);
        Plan produced=planner=="direct-union"?ProduceReference(x):
                      planner=="incremental"?Produce(x):ProduceRangeMin(x);
        byte[] certificate=JsonSerializer.SerializeToUtf8Bytes(Certificate(x,produced));
        Plan consumed;
        using(var stream=new MemoryStream(certificate,false))
        using(var doc=JsonDocument.Parse(stream)) consumed=ParsePlan(x,doc.RootElement);
        Output actual;int arenaBytes;
        using(var arena=new Arena(x)) {
            arenaBytes=arena.ArenaBytes;arena.Prepare(consumed);
            actual=arena.Execute(consumed);arena.Guards();
        }
        // This comparison is functional validation, not work hidden from a timer.
        Equal(actual.MandatoryValues,Expected(x));
        using(var certificateDocument=JsonDocument.Parse(certificate))
        return new {id,planner,objective="rho0-publication",checker="optimality",
            input_bytes=input.Length,certificate_bytes=certificate.Length,
            certificate=certificateDocument.RootElement.Clone(),
            actual_values=actual.MandatoryValues,actual_loads=actual.Loads,actual_bytes=actual.Bytes,
            publications=actual.Publications,descriptor_copies=actual.DescriptorCopies,
            sink=actual.Sink,arena_bytes=arenaBytes,passed=true};
    }
    public static void ExactDocumentWorkflow(string root,string output) {
        Directory.CreateDirectory(output);var all=LoadPolicyCases(root);int runs=0;
        using(var inputs=new StreamWriter(Path.Combine(output,"inputs.jsonl")))
        using(var records=new StreamWriter(Path.Combine(output,"executions.jsonl"))) {
            foreach(var c in all) {
                // A fixed, explicitly repriced input, not a native serving log.
                var node=JsonNode.Parse(c.Input.GetRawText());node["visit_weight"]=0;
                byte[] input=Encoding.UTF8.GetBytes(node.ToJsonString());
                using(var doc=JsonDocument.Parse(input))
                    inputs.WriteLine(JsonSerializer.Serialize(new {id=c.Trace.Id,suite=c.Suite,stratum=c.Stratum,
                        trace=doc.RootElement,input_utf8=Encoding.UTF8.GetString(input)}));
                foreach(string arm in new[]{"direct-union","incremental","range-min"}) {
                    records.WriteLine(JsonSerializer.Serialize(ReplayExactDocument(input,c.Trace.Id,arm)));++runs;
                }
            }
        }
        Need(all.Count==207&&runs==621,"whole retained document workflow");
        File.WriteAllText(Path.Combine(output,"summary.json"),JsonSerializer.Serialize(new {
            status="EXACT_DOCUMENT_FUNCTIONAL_PASSED",retained_inputs=200,separate_native_controls=7,
            native_executions=runs,planners=new[]{"direct-union","incremental","range-min"},
            same_serialized_input=true,same_full_optimality_guarantee=true,performance_measurements_started=false,
            acquisition="MemoryStream of retained UTF-8 input bytes; JSON decoding included functionally; disk/network acquisition excluded",
            path="acquire/decode/admit/plan/serialize-certificate/decode-certificate/strict-check/mask/index/allocate/materialize/native-execute/project/guards/free",
            limits="Synthetic sequential CPU lane arrays; no measured overhead, serving deployment, GPU or numerical attention claim"}));
    }
}
}
