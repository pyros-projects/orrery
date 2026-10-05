# Seam bench: orrery, Continuum and Motion Context on one reel (2026-10-05)

`reel.orr` (four 5 s scenes: two people walking and talking, music under it) made by `bench.py` with each tool on
identical settings (H3 ref2va int8, the 4-step turbo LoRA at 0.8, Comfy Kitchen attention, dpmpp_2m_sde / simple / 4
steps, 1024×576, 124 frames a clip, 22 frames of context, the same four clip texts), seeds 1–3: three seams each, nine
a tool. Every seam's value is set against the same quantity inside its own film: the median percentile over the nine
seams, how many reach p99, and the median value as a share of the film's inside p99. Continuum's chunks are 141 frames
(119 new), orrery's and Motion Context's 124 (102 new). Time for the reel: Continuum ~150 s in one run, orrery ~130 s
in four, Motion Context ~150 s in four.

| Tool | Seams | luma jump | luma pulse | pixel MAE | sound step | 20ms level dB |
|---|---|---|---|---|---|---|
| orrery | 9 | median p93, 2/9 ≥ p99, 0.55× p99 | median p90, 2/9 ≥ p99, 0.62× p99 | median p41, 0/9 ≥ p99, 0.30× p99 | median p70, 0/9 ≥ p99, 0.03× p99 | median p86, 0/9 ≥ p99, 0.24× p99 |
| continuum raw | 9 | median p78, 0/9 ≥ p99, 0.45× p99 | median p80, 0/9 ≥ p99, 0.34× p99 | median p76, 0/9 ≥ p99, 0.65× p99 | median p70, 0/9 ≥ p99, 0.03× p99 | median p80, 0/9 ≥ p99, 0.15× p99 |
| continuum repaired | 9 | median p78, 0/9 ≥ p99, 0.45× p99 | median p80, 0/9 ≥ p99, 0.34× p99 | median p76, 0/9 ≥ p99, 0.65× p99 | median p34, 0/9 ≥ p99, 0.01× p99 | median p54, 0/9 ≥ p99, 0.06× p99 |
| motion context | 9 | median p100, 9/9 ≥ p99, 3.22× p99 | median p100, 9/9 ≥ p99, 2.76× p99 | median p76, 1/9 ≥ p99, 0.52× p99 | median p69, 0/9 ≥ p99, 0.03× p99 | median p79, 0/9 ≥ p99, 0.16× p99 |

**What it shows.** Motion Context's picture jumps and flashes at every seam (9/9 above p99, ~3× the inside p99).
orrery is close to Continuum but behind: two of nine seams jump or flash in the picture (Continuum raw: none, the same
continuation), and Continuum's sound repair (Finalize Auto) lowers the clicks from p70 to p34 and the level jumps from
p80 to p54, where orrery has none. Continuum's picture repair changed nothing on these films. A lead for the picture:
Continuum copies the pinned latent back over the sampled one before it decodes (`v2/sequence.py:1225-1232`); orrery
decodes the sampler's slightly moved copy (it only checks the move, up to 1e-2).

Per seam values: the JSON below.

{
 "orrery": [
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.9839019775390625,
   "pixel MAE": 5.252018451690674,
   "luma pulse": 0.9042129516601562,
   "sound step": 0.0022975525353103876,
   "20ms level dB": 5.044843255172806,
   "percentile": {
    "luma jump": 99.5,
    "pixel MAE": 6.3,
    "luma pulse": 98.5,
    "sound step": 69.7,
    "20ms level dB": 86.1
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.7632923126220703,
    "pixel MAE": 17.357545852661133,
    "luma pulse": 0.9314996337890625,
    "sound step": 0.09492968767881393,
    "20ms level dB": 21.6091202019227
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 0.8846893310546875,
   "pixel MAE": 13.052379608154297,
   "luma pulse": 1.388824462890625,
   "sound step": 0.0017475932836532593,
   "20ms level dB": 9.829487325799565,
   "percentile": {
    "luma jump": 99.5,
    "pixel MAE": 84.3,
    "luma pulse": 100.0,
    "sound step": 66.7,
    "20ms level dB": 93.2
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.7632923126220703,
    "pixel MAE": 17.357545852661133,
    "luma pulse": 0.9314996337890625,
    "sound step": 0.09492968767881393,
    "20ms level dB": 21.6091202019227
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 0.6439437866210938,
   "pixel MAE": 17.310935974121094,
   "luma pulse": 0.9057693481445312,
   "sound step": 0.00040174275636672974,
   "20ms level dB": 8.508065643750339,
   "percentile": {
    "luma jump": 96.7,
    "pixel MAE": 98.8,
    "luma pulse": 98.5,
    "sound step": 32.1,
    "20ms level dB": 91.8
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.7632923126220703,
    "pixel MAE": 17.357545852661133,
    "luma pulse": 0.9314996337890625,
    "sound step": 0.09492968767881393,
    "20ms level dB": 21.6091202019227
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.6192169189453125,
   "pixel MAE": 5.182723045349121,
   "luma pulse": 0.6775741577148438,
   "sound step": 0.003454507328569889,
   "20ms level dB": 2.9843602435615124,
   "percentile": {
    "luma jump": 87.3,
    "pixel MAE": 16.7,
    "luma pulse": 75.6,
    "sound step": 79.3,
    "20ms level dB": 78.9
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.4534473419189453,
    "pixel MAE": 21.415040969848633,
    "luma pulse": 1.74161548614502,
    "sound step": 0.051422350108623505,
    "20ms level dB": 15.608224891881518
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 0.7947006225585938,
   "pixel MAE": 6.208158493041992,
   "luma pulse": 0.7585372924804688,
   "sound step": 6.993877468630672e-05,
   "20ms level dB": 6.763358435028051,
   "percentile": {
    "luma jump": 92.7,
    "pixel MAE": 27.5,
    "luma pulse": 81.6,
    "sound step": 10.1,
    "20ms level dB": 91.9
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.4534473419189453,
    "pixel MAE": 21.415040969848633,
    "luma pulse": 1.74161548614502,
    "sound step": 0.051422350108623505,
    "20ms level dB": 15.608224891881518
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 0.39701080322265625,
   "pixel MAE": 12.05308723449707,
   "luma pulse": 0.462371826171875,
   "sound step": 0.0031621090602129698,
   "20ms level dB": 2.5175195317960117,
   "percentile": {
    "luma jump": 73.5,
    "pixel MAE": 74.4,
    "luma pulse": 51.2,
    "sound step": 78.5,
    "20ms level dB": 74.8
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.4534473419189453,
    "pixel MAE": 21.415040969848633,
    "luma pulse": 1.74161548614502,
    "sound step": 0.051422350108623505,
    "20ms level dB": 15.608224891881518
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.715301513671875,
   "pixel MAE": 6.582304000854492,
   "luma pulse": 0.8171234130859375,
   "sound step": 0.00499328225851059,
   "20ms level dB": 4.692651732188601,
   "percentile": {
    "luma jump": 89.7,
    "pixel MAE": 40.6,
    "luma pulse": 89.6,
    "sound step": 76.8,
    "20ms level dB": 86.5
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.5776138305664062,
    "pixel MAE": 23.71476936340332,
    "luma pulse": 1.3135186004638677,
    "sound step": 0.08341085910797119,
    "20ms level dB": 19.49916786679354
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 0.473388671875,
   "pixel MAE": 5.14838981628418,
   "luma pulse": 0.5881576538085938,
   "sound step": 0.0026073534972965717,
   "20ms level dB": 10.689804513255368,
   "percentile": {
    "luma jump": 82.4,
    "pixel MAE": 13.4,
    "luma pulse": 73.4,
    "sound step": 70.4,
    "20ms level dB": 95.0
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.5776138305664062,
    "pixel MAE": 23.71476936340332,
    "luma pulse": 1.3135186004638677,
    "sound step": 0.08341085910797119,
    "20ms level dB": 19.49916786679354
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 1.3310012817382812,
   "pixel MAE": 11.859333038330078,
   "luma pulse": 1.8856353759765625,
   "sound step": 0.0023057707585394382,
   "20ms level dB": 2.5339890650313968,
   "percentile": {
    "luma jump": 97.2,
    "pixel MAE": 84.7,
    "luma pulse": 100.0,
    "sound step": 68.8,
    "20ms level dB": 72.4
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.5776138305664062,
    "pixel MAE": 23.71476936340332,
    "luma pulse": 1.3135186004638677,
    "sound step": 0.08341085910797119,
    "20ms level dB": 19.49916786679354
   }
  }
 ],
 "continuum raw": [
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.43901824951171875,
   "pixel MAE": 7.027495384216309,
   "luma pulse": 0.6588287353515625,
   "sound step": 0.00043070310493931174,
   "20ms level dB": 1.5599734467989221,
   "percentile": {
    "luma jump": 77.9,
    "pixel MAE": 35.7,
    "luma pulse": 81.4,
    "sound step": 41.6,
    "20ms level dB": 53.9
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11814779788255692,
    "20ms level dB": 27.72662226329296
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.4608154296875,
   "pixel MAE": 11.609542846679688,
   "luma pulse": 0.389892578125,
   "sound step": 0.00013373982801567763,
   "20ms level dB": 1.0774384098322591,
   "percentile": {
    "luma jump": 80.3,
    "pixel MAE": 80.7,
    "luma pulse": 44.7,
    "sound step": 19.3,
    "20ms level dB": 40.1
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11814779788255692,
    "20ms level dB": 27.72662226329296
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.7577056884765625,
   "pixel MAE": 11.217673301696777,
   "luma pulse": 0.694183349609375,
   "sound step": 0.003152696881443262,
   "20ms level dB": 5.509395617887493,
   "percentile": {
    "luma jump": 95.0,
    "pixel MAE": 77.7,
    "luma pulse": 83.8,
    "sound step": 70.3,
    "20ms level dB": 82.5
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11814779788255692,
    "20ms level dB": 27.72662226329296
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.33989715576171875,
   "pixel MAE": 7.0263824462890625,
   "luma pulse": 0.4900970458984375,
   "sound step": 0.003470722585916519,
   "20ms level dB": 1.5444343374525897,
   "percentile": {
    "luma jump": 61.8,
    "pixel MAE": 28.8,
    "luma pulse": 58.6,
    "sound step": 81.1,
    "20ms level dB": 56.4
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.04130197688937187,
    "20ms level dB": 21.74889915308121
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.12335968017578125,
   "pixel MAE": 9.69140338897705,
   "luma pulse": 0.563201904296875,
   "sound step": 6.59001525491476e-05,
   "20ms level dB": 3.3893573158159516,
   "percentile": {
    "luma jump": 26.5,
    "pixel MAE": 68.5,
    "luma pulse": 69.0,
    "sound step": 11.7,
    "20ms level dB": 79.9
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.04130197688937187,
    "20ms level dB": 21.74889915308121
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.8166961669921875,
   "pixel MAE": 11.184253692626953,
   "luma pulse": 0.8533096313476562,
   "sound step": 0.0026065215934067965,
   "20ms level dB": 4.379143425174278,
   "percentile": {
    "luma jump": 93.3,
    "pixel MAE": 81.1,
    "luma pulse": 87.2,
    "sound step": 78.4,
    "20ms level dB": 84.9
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.04130197688937187,
    "20ms level dB": 21.74889915308121
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.36029815673828125,
   "pixel MAE": 10.236949920654297,
   "luma pulse": 0.6356201171875,
   "sound step": 0.0026188648771494627,
   "20ms level dB": 4.082679249670738,
   "percentile": {
    "luma jump": 61.8,
    "pixel MAE": 76.3,
    "luma pulse": 79.6,
    "sound step": 74.7,
    "20ms level dB": 83.9
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07093046605587006,
    "20ms level dB": 22.012924748436827
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.36435699462890625,
   "pixel MAE": 10.312467575073242,
   "luma pulse": 0.3712158203125,
   "sound step": 0.0011271205730736256,
   "20ms level dB": 1.0660366675246804,
   "percentile": {
    "luma jump": 62.6,
    "pixel MAE": 77.1,
    "luma pulse": 40.7,
    "sound step": 61.2,
    "20ms level dB": 45.8
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07093046605587006,
    "20ms level dB": 22.012924748436827
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.9338111877441406,
   "pixel MAE": 10.145194053649902,
   "luma pulse": 0.8892326354980469,
   "sound step": 0.0020743655040860176,
   "20ms level dB": 3.3905918297658526,
   "percentile": {
    "luma jump": 98.3,
    "pixel MAE": 75.4,
    "luma pulse": 94.5,
    "sound step": 72.2,
    "20ms level dB": 79.9
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07093046605587006,
    "20ms level dB": 22.012924748436827
   }
  }
 ],
 "continuum repaired": [
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.43901824951171875,
   "pixel MAE": 7.027495384216309,
   "luma pulse": 0.6588287353515625,
   "sound step": 5.8154124417342246e-05,
   "20ms level dB": 1.0736633161869173,
   "percentile": {
    "luma jump": 77.9,
    "pixel MAE": 35.7,
    "luma pulse": 81.4,
    "sound step": 9.6,
    "20ms level dB": 39.8
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11795714497566223,
    "20ms level dB": 27.708284736208622
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.4608154296875,
   "pixel MAE": 11.609542846679688,
   "luma pulse": 0.389892578125,
   "sound step": 6.667761772405356e-05,
   "20ms level dB": 4.939901251465583,
   "percentile": {
    "luma jump": 80.3,
    "pixel MAE": 80.7,
    "luma pulse": 44.7,
    "sound step": 10.9,
    "20ms level dB": 81.1
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11795714497566223,
    "20ms level dB": 27.708284736208622
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.7577056884765625,
   "pixel MAE": 11.217673301696777,
   "luma pulse": 0.694183349609375,
   "sound step": 0.0006015319377183914,
   "20ms level dB": 3.778637691029742,
   "percentile": {
    "luma jump": 95.0,
    "pixel MAE": 77.7,
    "luma pulse": 83.8,
    "sound step": 48.5,
    "20ms level dB": 77.5
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 0.9342632293701172,
    "pixel MAE": 16.18890380859375,
    "luma pulse": 1.1349000549316406,
    "sound step": 0.11795714497566223,
    "20ms level dB": 27.708284736208622
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.33989715576171875,
   "pixel MAE": 7.0263824462890625,
   "luma pulse": 0.4900970458984375,
   "sound step": 0.0007083497475832701,
   "20ms level dB": 1.2101983016928932,
   "percentile": {
    "luma jump": 61.8,
    "pixel MAE": 28.8,
    "luma pulse": 58.6,
    "sound step": 59.9,
    "20ms level dB": 46.2
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.041245535016059875,
    "20ms level dB": 21.323280408168166
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.12335968017578125,
   "pixel MAE": 9.69140338897705,
   "luma pulse": 0.563201904296875,
   "sound step": 0.00017862099048215896,
   "20ms level dB": 2.795636447981657,
   "percentile": {
    "luma jump": 26.5,
    "pixel MAE": 68.5,
    "luma pulse": 69.0,
    "sound step": 27.6,
    "20ms level dB": 74.9
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.041245535016059875,
    "20ms level dB": 21.323280408168166
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.8166961669921875,
   "pixel MAE": 11.184253692626953,
   "luma pulse": 0.8533096313476562,
   "sound step": 0.0005667759105563164,
   "20ms level dB": 1.3393295269353078,
   "percentile": {
    "luma jump": 93.3,
    "pixel MAE": 81.1,
    "luma pulse": 87.2,
    "sound step": 54.8,
    "20ms level dB": 50.1
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.8004741668701172,
    "pixel MAE": 16.294992446899414,
    "luma pulse": 2.723281936645508,
    "sound step": 0.041245535016059875,
    "20ms level dB": 21.323280408168166
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 0.36029815673828125,
   "pixel MAE": 10.236949920654297,
   "luma pulse": 0.6356201171875,
   "sound step": 0.0001406812807545066,
   "20ms level dB": 1.3516039721637594,
   "percentile": {
    "luma jump": 61.8,
    "pixel MAE": 76.3,
    "luma pulse": 79.6,
    "sound step": 13.5,
    "20ms level dB": 54.2
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07095058262348175,
    "20ms level dB": 21.794571542411024
   }
  },
  {
   "frame": 243,
   "second": 10.125,
   "luma jump": 0.36435699462890625,
   "pixel MAE": 10.312467575073242,
   "luma pulse": 0.3712158203125,
   "sound step": 0.00040939764585345984,
   "20ms level dB": 1.4805223490684938,
   "percentile": {
    "luma jump": 62.6,
    "pixel MAE": 77.1,
    "luma pulse": 40.7,
    "sound step": 33.5,
    "20ms level dB": 57.4
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07095058262348175,
    "20ms level dB": 21.794571542411024
   }
  },
  {
   "frame": 362,
   "second": 15.083,
   "luma jump": 0.9338111877441406,
   "pixel MAE": 10.145194053649902,
   "luma pulse": 0.8892326354980469,
   "sound step": 0.0012955409474670887,
   "20ms level dB": 0.6279112834634668,
   "percentile": {
    "luma jump": 98.3,
    "pixel MAE": 75.4,
    "luma pulse": 94.5,
    "sound step": 64.5,
    "20ms level dB": 28.8
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.0399036407470703,
    "pixel MAE": 15.67755126953125,
    "luma pulse": 1.1954769134521486,
    "sound step": 0.07095058262348175,
    "20ms level dB": 21.794571542411024
   }
  }
 ],
 "motion context": [
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 4.592292785644531,
   "pixel MAE": 10.17629337310791,
   "luma pulse": 4.1437530517578125,
   "sound step": 0.006449330598115921,
   "20ms level dB": 3.917117117171724,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 58.5,
    "luma pulse": 100.0,
    "sound step": 76.3,
    "20ms level dB": 83.0
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 1.1313896179199219,
    "pixel MAE": 19.73907470703125,
    "luma pulse": 1.7339928436279315,
    "sound step": 0.10428749024868011,
    "20ms level dB": 21.895967985809495
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 5.970710754394531,
   "pixel MAE": 19.81657600402832,
   "luma pulse": 5.358604431152344,
   "sound step": 0.0036761234514415264,
   "20ms level dB": 3.061701792331515,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 98.8,
    "luma pulse": 100.0,
    "sound step": 72.0,
    "20ms level dB": 78.0
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 1.1313896179199219,
    "pixel MAE": 19.73907470703125,
    "luma pulse": 1.7339928436279315,
    "sound step": 0.10428749024868011,
    "20ms level dB": 21.895967985809495
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 10.1531982421875,
   "pixel MAE": 26.937448501586914,
   "luma pulse": 9.359519958496094,
   "sound step": 0.002662939950823784,
   "20ms level dB": 0.3317654219369575,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 100.0,
    "luma pulse": 100.0,
    "sound step": 68.9,
    "20ms level dB": 16.7
   },
   "seed": "s1",
   "inside_p99": {
    "luma jump": 1.1313896179199219,
    "pixel MAE": 19.73907470703125,
    "luma pulse": 1.7339928436279315,
    "sound step": 0.10428749024868011,
    "20ms level dB": 21.895967985809495
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 2.9511642456054688,
   "pixel MAE": 8.659269332885742,
   "luma pulse": 2.3793792724609375,
   "sound step": 0.00018974440172314644,
   "20ms level dB": 5.301340418355278,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 39.0,
    "luma pulse": 100.0,
    "sound step": 22.7,
    "20ms level dB": 86.4
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.6078224182128906,
    "pixel MAE": 23.360740661621094,
    "luma pulse": 1.6486730957031277,
    "sound step": 0.06852040439844131,
    "20ms level dB": 18.69994480386407
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 1.9378814697265625,
   "pixel MAE": 7.213632583618164,
   "luma pulse": 1.7350387573242188,
   "sound step": 0.0010983222164213657,
   "20ms level dB": 2.9289512747369253,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 28.6,
    "luma pulse": 99.0,
    "sound step": 61.8,
    "20ms level dB": 75.2
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.6078224182128906,
    "pixel MAE": 23.360740661621094,
    "luma pulse": 1.6486730957031277,
    "sound step": 0.06852040439844131,
    "20ms level dB": 18.69994480386407
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 5.1845550537109375,
   "pixel MAE": 15.342888832092285,
   "luma pulse": 4.594753265380859,
   "sound step": 0.0100740110501647,
   "20ms level dB": 0.9364718522373743,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 86.4,
    "luma pulse": 100.0,
    "sound step": 82.0,
    "20ms level dB": 37.2
   },
   "seed": "s2",
   "inside_p99": {
    "luma jump": 1.6078224182128906,
    "pixel MAE": 23.360740661621094,
    "luma pulse": 1.6486730957031277,
    "sound step": 0.06852040439844131,
    "20ms level dB": 18.69994480386407
   }
  },
  {
   "frame": 124,
   "second": 5.167,
   "luma jump": 4.2114715576171875,
   "pixel MAE": 10.978790283203125,
   "luma pulse": 3.9292373657226562,
   "sound step": 0.0011842567473649979,
   "20ms level dB": 5.675358134870368,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 73.5,
    "luma pulse": 100.0,
    "sound step": 57.4,
    "20ms level dB": 90.0
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.4568233489990234,
    "pixel MAE": 23.68252182006836,
    "luma pulse": 1.4860824584960939,
    "sound step": 0.0887875184416771,
    "20ms level dB": 17.520581132450165
   }
  },
  {
   "frame": 226,
   "second": 9.417,
   "luma jump": 4.668792724609375,
   "pixel MAE": 11.84013843536377,
   "luma pulse": 4.1057281494140625,
   "sound step": 0.0007034823065623641,
   "20ms level dB": 2.7701159775679014,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 76.1,
    "luma pulse": 100.0,
    "sound step": 42.7,
    "20ms level dB": 78.6
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.4568233489990234,
    "pixel MAE": 23.68252182006836,
    "luma pulse": 1.4860824584960939,
    "sound step": 0.0887875184416771,
    "20ms level dB": 17.520581132450165
   }
  },
  {
   "frame": 328,
   "second": 13.667,
   "luma jump": 5.2982940673828125,
   "pixel MAE": 15.40836238861084,
   "luma pulse": 4.827301025390625,
   "sound step": 0.004903214983642101,
   "20ms level dB": 5.8050096318540145,
   "percentile": {
    "luma jump": 100.0,
    "pixel MAE": 85.7,
    "luma pulse": 100.0,
    "sound step": 76.7,
    "20ms level dB": 90.1
   },
   "seed": "s3",
   "inside_p99": {
    "luma jump": 1.4568233489990234,
    "pixel MAE": 23.68252182006836,
    "luma pulse": 1.4860824584960939,
    "sound step": 0.0887875184416771,
    "20ms level dB": 17.520581132450165
   }
  }
 ]
}
