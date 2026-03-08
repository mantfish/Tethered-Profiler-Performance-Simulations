%%
% This script works out the patch mappings for the Argo float geometry
% which is implemented as IGDEF=36 on the FVM WAMIT server. 
%
% This is a circular cylinder with a foam box on top. Two symmetry axes are
% exploited so only 1/4 of the geometry is created. 
%
% Written by H.B. Bingham, DTU, May, 2025. 
%
%%
% The floater dimensions. 
%
R=0.055;            % cylinder radius
DraftCyl=1.325;     % cylinder draft from the top of the box
L=0.21;             % box side length
Draft=0.125;        % box draft
Rt=0.025;            % Top buoyancy cylinder radius
DraftCtop=.025;     % Draft of the top cylinder
%
% Volume and radii of gyration
%
Vol=L^2*Draft+pi*R^2*(DraftCyl-Draft)+pi*Rt^2*DraftCtop;  % volume
r55=sqrt(1/4*R^2+1/3*DraftCyl^2)       % roll and pitch radius of gyration for a solid cylinder
r66=sqrt(1/2*R^2)                      % yaw radius of gyration for a solid cylinder
%
%%
% Patch 1, the box end
np=5; u=-1+2*[0:np-1]/(np-1);
[U,V]=meshgrid(u,u);

X=L/2*ones(np);
Y=L/4*(U+1);
Z=-Draft/2*(V+1)-DraftCtop;

figure(1); clf; hold on
mesh(X,Y,Z)
xlabel('x'); ylabel('y'); zlabel('z')
view(-22,28)
% Compute and plot the normal vectors to ensure they point into the body.
for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(2).v=L/4*ones(np);
Xv(3).v=-Draft/2*ones(np);
[nvec,H]=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 2, the box side

X=-L/4*(U-1);
Y=L/2*ones(np);
Z=-Draft/2*(V+1)-DraftCtop;

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-L/4*ones(np);
Xv(3).v=-Draft/2*ones(np);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 3, the box bottom front patch

th=pi/8*(V+1);
R0=L/2./cos(th);
r=R0-(R0-R)/2.*(1-U);
X=r.*cos(th);
Y=r.*sin(th);
Z=(-Draft-DraftCtop)*ones(np);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=(R0-R)/2.*cos(th);
Xu(2).v=(R0-R)/2.*sin(th);
Xv(1).v=-pi/8*R/2*(1-U)*sin(th);
Xv(2).v=pi/8*(R/2*(1-U).*cos(th)+L/4*(1+U)*sec(th).^2);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 4, the box bottom rear patch

th=pi/8*(V+3);
R0=L/2./sin(th);
r=R0-(R0-R)/2.*(1-U);
X=r.*cos(th);
Y=r.*sin(th);
Z=(-Draft-DraftCtop)*ones(np);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=L/4-R/2*cos(th);
Xu(2).v=L/4-R/2*sin(th);
Xv(1).v=-pi/8*(L/4*(1+U)+L/4*(1+U).*cot(th).^2-R/2*(-1+U).*sin(th));
% Xv(1).v=pi/8*(R/2*(-1+U).*sin(th)-L/4*(1+U)*csc(th).^2);
Xv(2).v=pi/8*R/2*(1-U).*cos(th);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 5, the cylinder body

th=pi/4*(1+U);
X=R*cos(th);
Y=R*sin(th);
Z=-Draft-(DraftCyl-Draft)/2*(V+1)-DraftCtop;

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-pi/4*Y;
Xu(2).v=pi/4*X;
Xv(3).v=-.5*(DraftCyl-Draft);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 6, the cylinder bottom

th=pi/4*(1+U);
X=R/2*(1-V).*cos(th);
Y=R/2*(1-V).*sin(th);
Z=(-DraftCyl-DraftCtop)*ones(np);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-pi/4*Y;
Xu(2).v=pi/4*X;
Xv(1).v=-R/2*cos(th);
Xv(2).v=-R/2*sin(th);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

axis equal

% Patch 7, the box top front patch

th=pi/8*(V+1);
R0=L/2./cos(th);
r=R0-(R0-Rt)/2.*(U+1);
X=r.*cos(th);
Y=r.*sin(th);
Z=(-DraftCtop)*ones(np);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-L/4+Rt/2.*cos(th);
Xu(2).v=-L/4+Rt/2.*sin(th);
Xv(1).v=pi/8*Rt/2*(1+U)*sin(th);
Xv(2).v=pi/8*(Rt/2*(1+U).*cos(th)+L/4*(1-U)*sec(th).^2);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 8, the box top rear patch

th=pi/8*(V+3);
R0=L/2./sin(th);
r=R0-(R0-Rt)/2.*(1+U);
X=r.*cos(th);
Y=r.*sin(th);
Z=(-DraftCtop)*ones(np);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-L/4+Rt/2*sin(th);
Xu(2).v=-L/4+Rt/2*cos(th);
Xv(1).v=pi/16./sin(th).^2.*(L/2*(-1+U)-3*Rt/4*(1+U).*sin(th)+Rt/4*(1+U).*sin(3*th));
Xv(2).v=pi/8*Rt/2*(1+U).*cos(th);
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)

% Patch 9, the top cylinder body

th=pi/4*(1+U);
X=Rt*cos(th);
Y=Rt*sin(th);
Z=-DraftCtop/2*(V+1);

mesh(X,Y,Z)

for i=1:3
    Xu(i).v=zeros(np); Xv(i).v=zeros(np);
end
Xu(1).v=-pi/4*Y;
Xu(2).v=pi/4*X;
Xv(3).v=-.5*DraftCtop;
nvec=ComputeNormals(Xu,Xv);
quiver3(X,Y,Z,nvec(1).v,nvec(2).v,nvec(3).v)
