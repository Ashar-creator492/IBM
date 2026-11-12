"""Bundle current Python source for the upload-based Colab notebook."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
output=root/'output/colab/q_route_gpu_source.zip'
output.parent.mkdir(parents=True,exist_ok=True)
paths=sorted([*root.glob('ibm_qiskit/*.py'),*root.glob('api/*.py'),*root.glob('requirements*.txt')])
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(path,path.relative_to(root))
print(output)
